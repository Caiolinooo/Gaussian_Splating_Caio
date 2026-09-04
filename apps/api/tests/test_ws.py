"""WebSocket progress bridge: snapshot first, clean close on done, isolation."""

from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.jwtutil import encode_hs256
from app.main import create_app
from tests.conftest import TEST_JWT_SECRET, build_fake_runtime, make_settings
from tests.helpers import job_form, video_files


def _token(user_id: str) -> str:
    return encode_hs256({"sub": user_id, "role": "authenticated", "exp": int(time.time()) + 3600}, TEST_JWT_SECRET)


def test_ws_sends_snapshot_and_closes_when_done(tmp_path) -> None:
    settings = make_settings(tmp_path)
    runtime = build_fake_runtime(settings)
    app = create_app(settings_override=settings, runtime=runtime)
    token = _token("user-a")
    with TestClient(app) as client:
        created = client.post(
            "/jobs",
            files=video_files(),
            data=job_form(key="ws-done"),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        for _ in range(50):
            detail = client.get(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
            if detail.json()["state"] == "done":
                break
            time.sleep(0.05)
        with client.websocket_connect(
            f"/jobs/{job_id}/events?token={token}",
        ) as websocket:
            snapshot = websocket.receive_json()
            assert snapshot["job_id"] == job_id
            assert snapshot["state"] == "done"
            assert "overall_progress" in snapshot


def test_ws_streams_fake_progress(tmp_path) -> None:
    settings = make_settings(tmp_path)
    runtime = build_fake_runtime(settings)
    hold = threading.Event()
    runtime.machine.block_run = hold
    app = create_app(settings_override=settings, runtime=runtime)
    token = _token("user-a")
    try:
        with TestClient(app) as client:
            created = client.post(
                "/jobs",
                files=video_files(),
                data=job_form(key="ws-live"),
                headers={"Authorization": f"Bearer {token}"},
            )
            job_id = created.json()["job_id"]
            with client.websocket_connect(f"/jobs/{job_id}/events?token={token}") as websocket:
                first = websocket.receive_json()
                assert first["job_id"] == job_id
                assert first["state"] in {"queued", "extracting"}
                hold.set()
                saw_done = first["state"] == "done"
                for _ in range(20):
                    if saw_done:
                        break
                    event = websocket.receive_json()
                    if event["state"] == "done":
                        saw_done = True
                assert saw_done
    finally:
        hold.set()


def test_ws_forbidden_for_other_user(tmp_path) -> None:
    settings = make_settings(tmp_path)
    runtime = build_fake_runtime(settings)
    app = create_app(settings_override=settings, runtime=runtime)
    token_a = _token("user-a")
    token_b = _token("user-b")
    with TestClient(app) as client:
        created = client.post(
            "/jobs",
            files=video_files(),
            data=job_form(key="ws-iso"),
            headers={"Authorization": f"Bearer {token_a}"},
        )
        job_id = created.json()["job_id"]
        with client.websocket_connect(f"/jobs/{job_id}/events?token={token_b}") as websocket:
            try:
                websocket.receive_json()
                raise AssertionError("other user must not receive job events")
            except WebSocketDisconnect as exc:
                assert exc.code == 4403


def test_ws_accepts_access_token_query(tmp_path) -> None:
    settings = make_settings(tmp_path)
    runtime = build_fake_runtime(settings)
    app = create_app(settings_override=settings, runtime=runtime)
    token = _token("user-a")
    with TestClient(app) as client:
        created = client.post(
            "/jobs",
            files=video_files(),
            data=job_form(key="ws-access"),
            headers={"Authorization": f"Bearer {token}"},
        )
        job_id = created.json()["job_id"]
        with client.websocket_connect(f"/jobs/{job_id}/events?access_token={token}") as websocket:
            snapshot = websocket.receive_json()
            assert snapshot["job_id"] == job_id


def test_ws_rejects_missing_token(tmp_path) -> None:
    settings = make_settings(tmp_path, dev_auth_bypass=False)
    runtime = build_fake_runtime(settings)
    app = create_app(settings_override=settings, runtime=runtime)
    token = _token("user-a")
    with TestClient(app) as client:
        created = client.post(
            "/jobs",
            files=video_files(),
            data=job_form(key="ws-auth"),
            headers={"Authorization": f"Bearer {token}"},
        )
        job_id = created.json()["job_id"]
        with client.websocket_connect(f"/jobs/{job_id}/events") as websocket:
            try:
                websocket.receive_json()
                raise AssertionError("unauthenticated socket must close")
            except WebSocketDisconnect as exc:
                assert exc.code == 4401
