"""Artifact download and path-traversal rejection."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from tests.helpers import job_form, video_files


def _plant_artifacts(work_dir: Path) -> None:
    export = work_dir / "export"
    thumbs = export / "thumbnails"
    thumbs.mkdir(parents=True, exist_ok=True)
    (export / "master.ply").write_bytes(b"ply-bytes")
    (export / "scene.ksplat").write_bytes(b"ksplat-bytes")
    (export / "scene.json").write_text('{"schemaVersion":1}', encoding="utf-8")
    (export / "scene.zip").write_bytes(b"zip-bytes")
    (thumbs / "preview.jpg").write_bytes(b"jpeg-bytes")


def test_download_known_artifacts(client_as, runtime) -> None:
    with client_as("user-a") as client:
        created = client.post("/jobs", files=video_files(), data=job_form(key="art-1"))
        job_id = created.json()["job_id"]
        record = runtime.machine.get(job_id)
        _plant_artifacts(record.work_path)

        ply = client.get(f"/jobs/{job_id}/artifacts/ply")
        assert ply.status_code == 200
        assert ply.content == b"ply-bytes"

        ksplat = client.get(f"/jobs/{job_id}/artifacts/ksplat")
        assert ksplat.status_code == 200
        assert ksplat.content == b"ksplat-bytes"

        thumb = client.get(f"/jobs/{job_id}/artifacts/thumbnail")
        assert thumb.status_code == 200
        assert thumb.content == b"jpeg-bytes"

        scene = client.get(f"/jobs/{job_id}/artifacts/scene")
        assert scene.status_code == 200
        assert b"schemaVersion" in scene.content

        package = client.get(f"/jobs/{job_id}/artifacts/package")
        assert package.status_code == 200
        assert package.content == b"zip-bytes"


def test_download_log_artifact(client_as, runtime) -> None:
    with client_as("user-a") as client:
        created = client.post("/jobs", files=video_files(), data=job_form(key="art-log"))
        job_id = created.json()["job_id"]
        record = runtime.machine.get(job_id)
        colmap_dir = record.work_path / "colmap"
        colmap_dir.mkdir(parents=True, exist_ok=True)
        (colmap_dir / "colmap.log").write_text("registro técnico", encoding="utf-8")

        response = client.get(f"/jobs/{job_id}/artifacts/log")
        assert response.status_code == 200
        assert response.text == "registro técnico"
        assert response.headers["content-type"].startswith("text/plain")


def test_log_artifact_missing_is_404(client_as) -> None:
    with client_as("user-a") as client:
        created = client.post("/jobs", files=video_files(), data=job_form(key="art-log-404"))
        job_id = created.json()["job_id"]
        response = client.get(f"/jobs/{job_id}/artifacts/log")
    assert response.status_code == 404


def test_artifact_kind_rejects_traversal(client_as) -> None:
    with client_as("user-a") as client:
        created = client.post("/jobs", files=video_files(), data=job_form(key="art-trav"))
        job_id = created.json()["job_id"]
        response = client.get(f"/jobs/{job_id}/artifacts/..%2F..%2Fsecret")
    assert response.status_code in {404, 422}


def test_artifact_missing_is_404(client_as) -> None:
    with client_as("user-a") as client:
        created = client.post("/jobs", files=video_files(), data=job_form(key="art-miss"))
        job_id = created.json()["job_id"]
        response = client.get(f"/jobs/{job_id}/artifacts/ply")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ARTIFACT_NOT_READY"


def test_other_user_cannot_download_artifact(client_as, app, runtime) -> None:
    with client_as("user-a") as client:
        created = client.post("/jobs", files=video_files(), data=job_form(key="art-iso"))
        job_id = created.json()["job_id"]
        _plant_artifacts(runtime.machine.get(job_id).work_path)

    async def _user_b() -> CurrentUser:
        return CurrentUser(user_id="user-b")

    app.dependency_overrides[get_current_user] = _user_b
    with TestClient(app) as client_b:
        assert client_b.get(f"/jobs/{job_id}/artifacts/ply").status_code == 403
