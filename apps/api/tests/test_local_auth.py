"""Login local: /auth/local + /auth/login com usuário configurado por env."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.jwtutil import decode_unverified
from app.main import create_app
from tests.conftest import build_fake_runtime, make_settings


def _local_settings(tmp_path, user: str = "caio", password: str = "Caio@2122@"):
    settings = make_settings(tmp_path, dev_auth_bypass=False)
    settings.local_auth_user = user
    settings.local_auth_password = password
    return settings


def test_local_auth_info_disabled_when_not_configured(tmp_path) -> None:
    settings = make_settings(tmp_path, dev_auth_bypass=False)
    app = create_app(settings_override=settings, runtime=build_fake_runtime(settings))
    with TestClient(app) as client:
        response = client.get("/auth/local")
    assert response.status_code == 200
    assert response.json() == {"enabled": False, "username": None}


def test_local_auth_info_exposes_username_never_password(tmp_path) -> None:
    settings = _local_settings(tmp_path)
    app = create_app(settings_override=settings, runtime=build_fake_runtime(settings))
    with TestClient(app) as client:
        response = client.get("/auth/local")
    assert response.status_code == 200
    body = response.json()
    assert body == {"enabled": True, "username": "caio"}
    assert "Caio@2122@" not in response.text


def test_local_login_rejects_wrong_password(tmp_path) -> None:
    settings = _local_settings(tmp_path)
    app = create_app(settings_override=settings, runtime=build_fake_runtime(settings))
    with TestClient(app) as client:
        response = client.post("/auth/login", json={"username": "caio", "password": "errada-123"})
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_local_login_rejects_unknown_user(tmp_path) -> None:
    settings = _local_settings(tmp_path)
    app = create_app(settings_override=settings, runtime=build_fake_runtime(settings))
    with TestClient(app) as client:
        response = client.post("/auth/login", json={"username": "admin", "password": "Caio@2122@"})
    assert response.status_code == 401


def test_local_login_disabled_returns_422(tmp_path) -> None:
    settings = make_settings(tmp_path, dev_auth_bypass=False)
    app = create_app(settings_override=settings, runtime=build_fake_runtime(settings))
    with TestClient(app) as client:
        response = client.post("/auth/login", json={"username": "caio", "password": "Caio@2122@"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "LOCAL_AUTH_DISABLED"


def test_local_login_token_accesses_jobs_as_local_user(tmp_path) -> None:
    settings = _local_settings(tmp_path)
    app = create_app(settings_override=settings, runtime=build_fake_runtime(settings))
    with TestClient(app) as client:
        login = client.post("/auth/login", json={"username": "caio", "password": "Caio@2122@"})
        assert login.status_code == 200
        body = login.json()
        assert body["token_type"] == "bearer"
        assert body["user"]["id"] == "caio"

        _header, claims = decode_unverified(body["access_token"])
        assert claims["sub"] == "caio"
        assert claims["aud"] == "authenticated"

        jobs = client.get("/jobs", headers={"Authorization": f"Bearer {body['access_token']}"})
        assert jobs.status_code == 200
        assert jobs.json()["jobs"] == []
