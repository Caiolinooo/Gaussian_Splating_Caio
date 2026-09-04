"""Testes básicos da API (Fase 0): liveness, pré-checagens e fluxo de provisionamento."""

import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

EXPECTED_COMPONENTS = {"gpu", "wsl2", "disk", "memory", "ffmpeg", "colmap", "python"}


def test_health_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"]
    assert body["version"]


def test_setup_status_shape() -> None:
    response = client.get("/setup/status")
    assert response.status_code == 200
    body = response.json()
    keys = {check["key"] for check in body["checks"]}
    assert EXPECTED_COMPONENTS <= keys
    assert body["overall"] in {"ok", "warning", "error", "missing", "unknown"}
    assert isinstance(body["ready"], bool)


def test_install_flow_and_progress() -> None:
    response = client.post("/setup/install")
    assert response.status_code == 202

    progress = client.get("/setup/progress").json()
    for _ in range(200):
        if progress["state"] in ("done", "error"):
            break
        time.sleep(0.1)
        progress = client.get("/setup/progress").json()

    assert progress["state"] == "done"
    assert progress["percent"] == 100
    statuses = {step["key"]: step["status"] for step in progress["steps"]}
    assert statuses["detect"] == "done"
    assert statuses["ffmpeg"] == "skipped"  # stub da Fase 0
    assert statuses["gsplat"] == "skipped"  # stub da Fase 0
    assert progress["log"]


def test_install_conflict_while_running() -> None:
    # Garante estado "running" iniciando um provisionamento e batendo de novo imediatamente.
    first = client.post("/setup/install")
    if first.status_code == 202:
        second = client.post("/setup/install")
        assert second.status_code in (202, 409)
        if second.status_code == 409:
            assert "andamento" in second.json()["detail"]
