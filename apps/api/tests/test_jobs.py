"""Job upload, listing, isolation, cancel and retry."""

from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.main import create_app
from tests.conftest import build_fake_runtime, make_settings
from tests.fakes import FakeJobMachine, FakeRecord, FakeSource, FakeStage
from tests.helpers import gif_files, image_files, job_form, ply_files, video_files


def test_upload_video_returns_202(client_as) -> None:
    with client_as("user-a") as client:
        response = client.post("/jobs", files=video_files(), data=job_form(key="video-1"))
    assert response.status_code == 202
    body = response.json()
    assert body["job_id"]
    assert body["state"] == "queued"


def test_upload_images_returns_202(client_as) -> None:
    with client_as("user-a") as client:
        response = client.post("/jobs", files=image_files(20), data=job_form(key="imgs-1"))
    assert response.status_code == 202
    assert response.json()["state"] == "queued"


def test_upload_gif_returns_202(client_as, runtime) -> None:
    with client_as("user-a") as client:
        response = client.post("/jobs", files=gif_files(), data=job_form(key="gif-1"))
    assert response.status_code == 202
    record = runtime.machine.get(response.json()["job_id"])
    assert record.source.kind == "gif"


def test_upload_ply_returns_202(client_as, runtime) -> None:
    with client_as("user-a") as client:
        response = client.post("/jobs", files=ply_files(), data=job_form(key="ply-1"))
    assert response.status_code == 202
    record = runtime.machine.get(response.json()["job_id"])
    assert record.source.kind == "ply"


def test_upload_rejects_invalid_ply_header(client_as) -> None:
    with client_as("user-a") as client:
        response = client.post(
            "/jobs",
            files={"file": ("scan.ply", b"not-a-ply", "application/octet-stream")},
            data=job_form(key="bad-ply"),
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_PLY"


def test_upload_rejects_invalid_video_extension(client_as) -> None:
    with client_as("user-a") as client:
        response = client.post(
            "/jobs",
            files={"file": ("notes.txt", b"nope", "text/plain")},
            data=job_form(key="bad-ext"),
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_VIDEO_EXTENSION"


def test_upload_rejects_non_positive_height(client_as) -> None:
    with client_as("user-a") as client:
        response = client.post("/jobs", files=video_files(), data=job_form(height="0", key="h0"))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_HEIGHT"


def test_upload_rejects_negative_height(client_as) -> None:
    with client_as("user-a") as client:
        response = client.post("/jobs", files=video_files(), data=job_form(height="-1", key="hneg"))
    assert response.status_code == 422
    assert "maior que zero" in response.json()["detail"]["message"]


def test_upload_rejects_too_few_images(client_as) -> None:
    with client_as("user-a") as client:
        response = client.post("/jobs", files=image_files(3), data=job_form(key="few"))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "TOO_FEW_IMAGES"


def test_user_isolation_on_get_cancel_retry(client_as, app) -> None:
    with client_as("user-a") as client:
        created = client.post("/jobs", files=video_files(), data=job_form(key="iso-a"))
        assert created.status_code == 202
        job_id = created.json()["job_id"]

    async def _user_b() -> CurrentUser:
        return CurrentUser(user_id="user-b")

    app.dependency_overrides[get_current_user] = _user_b
    with TestClient(app) as client_b:
        listed = client_b.get("/jobs")
        assert listed.status_code == 200
        assert listed.json()["jobs"] == []
        assert client_b.get(f"/jobs/{job_id}").status_code == 403
        assert client_b.post(f"/jobs/{job_id}/cancel").status_code == 403
        assert client_b.post(f"/jobs/{job_id}/retry").status_code == 403
        assert client_b.get(f"/jobs/{job_id}/artifacts/ply").status_code == 403
        assert client_b.delete(f"/jobs/{job_id}").status_code == 403


def test_owner_can_list_and_get_detail(client_as) -> None:
    with client_as("user-a") as client:
        created = client.post("/jobs", files=video_files(), data=job_form(key="detail-1"))
        job_id = created.json()["job_id"]
        listed = client.get("/jobs")
        assert listed.status_code == 200
        assert listed.json()["jobs"][0]["job_id"] == job_id
        detail = client.get(f"/jobs/{job_id}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["user_height_m"] == 1.75
        assert {stage["name"] for stage in body["stages"]} >= {
            "extracting",
            "sfm",
            "training",
            "exporting",
            "meshproxy",
            "autocal",
        }


def test_cancel_queued_job(client_as, runtime) -> None:
    runtime.machine.block_run = threading.Event()
    try:
        with client_as("user-a") as client:
            created = client.post("/jobs", files=video_files(), data=job_form(key="cancel-1"))
            job_id = created.json()["job_id"]
            cancelled = client.post(f"/jobs/{job_id}/cancel")
            assert cancelled.status_code == 200
            assert cancelled.json()["state"] in {"cancelled", "queued"}
    finally:
        runtime.machine.block_run.set()


def test_rebuild_done_job(client_as, runtime) -> None:
    with client_as("user-a") as client:
        created = client.post("/jobs", files=video_files(), data=job_form(key="rebuild-1"))
        job_id = created.json()["job_id"]
        record = runtime.machine.get(job_id)
        record.state = "done"
        accepted = client.post(f"/jobs/{job_id}/rebuild")
        assert accepted.status_code == 202
        assert accepted.json()["job_id"] == job_id
        assert runtime.machine.get(job_id).state == "sfm"


def test_retry_only_when_error_or_cancelled(client_as, runtime) -> None:
    with client_as("user-a") as client:
        created = client.post("/jobs", files=video_files(), data=job_form(key="retry-1"))
        job_id = created.json()["job_id"]
        record = runtime.machine.get(job_id)
        record.state = "extracting"
        rejected = client.post(f"/jobs/{job_id}/retry")
        assert rejected.status_code == 422
        record.state = "error"
        accepted = client.post(f"/jobs/{job_id}/retry")
        assert accepted.status_code == 202
        assert accepted.json()["job_id"] == job_id


def test_supervisor_resumes_running_jobs_on_boot(tmp_path) -> None:
    settings = make_settings(tmp_path)
    machine = FakeJobMachine()
    stamp = "2026-09-04T12:00:00+00:00"
    job_id = "resume-me"
    work = settings.resolved_data_root() / "user-a" / job_id
    work.mkdir(parents=True)
    machine.jobs[job_id] = FakeRecord(
        job_id=job_id,
        user_id="user-a",
        state="training",
        source=FakeSource(kind="video", paths=["a.mp4"]),
        work_dir=str(work),
        user_height_m=1.75,
        created_at=stamp,
        updated_at=stamp,
        stages={
            name: FakeStage(name=name)
            for name in ("extracting", "sfm", "training", "exporting", "meshproxy", "autocal")
        },
    )
    runtime = build_fake_runtime(settings, machine)
    app = create_app(settings_override=settings, runtime=runtime)
    with TestClient(app) as client:
        deadline = time.time() + 3
        while time.time() < deadline and machine.get(job_id).state != "done":
            time.sleep(0.05)
        assert machine.get(job_id).state == "done"
        assert job_id in machine.run_calls
        assert client.get("/health").status_code == 200


def test_idempotent_create_reuses_job(client_as) -> None:
    with client_as("user-a") as client:
        first = client.post("/jobs", files=video_files(), data=job_form(key="same-key"))
        second = client.post("/jobs", files=video_files(), data=job_form(key="same-key"))
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]


def test_owner_can_delete_job(client_as) -> None:
    with client_as("user-a") as client:
        created = client.post("/jobs", files=video_files(), data=job_form(key="del-1"))
        job_id = created.json()["job_id"]
        deleted = client.delete(f"/jobs/{job_id}")
        assert deleted.status_code == 204
        assert deleted.content == b""
        assert client.get(f"/jobs/{job_id}").status_code == 404
        listed = client.get("/jobs")
        assert listed.json()["jobs"] == []
