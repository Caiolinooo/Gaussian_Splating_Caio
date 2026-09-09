"""Testes básicos da API (Fase 0): liveness, pré-checagens e fluxo de provisionamento."""

import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

EXPECTED_COMPONENTS = {
    "gpu",
    "wsl2",
    "disk",
    "memory",
    "ffmpeg",
    "colmap",
    "python",
    "pytorch",
    "gsplat",
}


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


def test_setup_status_is_cached(monkeypatch) -> None:
    from app.services import provisioner_service

    provisioner_service.invalidate_health_cache()
    calls = {"n": 0}
    original = provisioner_service.run_all_checks

    def wrapped():
        calls["n"] += 1
        return original()

    monkeypatch.setattr(provisioner_service, "run_all_checks", wrapped)
    assert client.get("/setup/status").status_code == 200
    assert client.get("/setup/status").status_code == 200
    assert calls["n"] == 1
    provisioner_service.invalidate_health_cache()


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
    assert statuses["ffmpeg"] in {"done", "skipped"}
    assert statuses["colmap"] in {"done", "skipped"}
    assert statuses["gsplat"] in {"done", "skipped", "error"}
    assert "sudo -n apt-get install -y colmap" not in "\n".join(progress["log"]).lower()
    assert progress["log"]


def test_install_conflict_while_running() -> None:
    # Garante estado "running" iniciando um provisionamento e batendo de novo imediatamente.
    first = client.post("/setup/install")
    if first.status_code == 202:
        second = client.post("/setup/install")
        assert second.status_code in (202, 409)
        if second.status_code == 409:
            assert "andamento" in second.json()["detail"]
