"""Auth: 401 without token, HS256 JWT, and DEV_AUTH_BYPASS."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.core.jwtutil import encode_hs256
from app.main import create_app
from tests.conftest import TEST_JWT_SECRET, build_fake_runtime, make_settings
from tests.helpers import bearer


def test_jobs_unauthorized_without_token(tmp_path) -> None:
    settings = make_settings(tmp_path, dev_auth_bypass=False)
    app = create_app(settings_override=settings, runtime=build_fake_runtime(settings))
    with TestClient(app) as client:
        response = client.get("/jobs")
    assert response.status_code == 401
    body = response.json()["detail"]
    assert body["code"] == "UNAUTHENTICATED"
    assert "Não autenticado" in body["message"]


def test_jobs_unauthorized_invalid_token(tmp_path) -> None:
    settings = make_settings(tmp_path, dev_auth_bypass=False)
    app = create_app(settings_override=settings, runtime=build_fake_runtime(settings))
    with TestClient(app) as client:
        response = client.get("/jobs", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "TOKEN_INVALID"


def test_jobs_accepts_valid_hs256_jwt(tmp_path) -> None:
    settings = make_settings(tmp_path, dev_auth_bypass=False)
    app = create_app(settings_override=settings, runtime=build_fake_runtime(settings))
    with TestClient(app) as client:
        response = client.get("/jobs", headers=bearer("user-jwt"))
    assert response.status_code == 200
    assert response.json()["jobs"] == []


def test_expired_token_is_rejected(tmp_path) -> None:
    settings = make_settings(tmp_path, dev_auth_bypass=False)
    app = create_app(settings_override=settings, runtime=build_fake_runtime(settings))
    token = encode_hs256(
        {"sub": "user-jwt", "exp": int(time.time()) - 120},
        TEST_JWT_SECRET,
    )
    with TestClient(app) as client:
        response = client.get("/jobs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "TOKEN_EXPIRED"


def test_dev_auth_bypass_uses_fixed_user(tmp_path) -> None:
    settings = make_settings(tmp_path, dev_auth_bypass=True)
    app = create_app(settings_override=settings, runtime=build_fake_runtime(settings))
    with TestClient(app) as client:
        response = client.get("/jobs")
    assert response.status_code == 200
    assert response.json()["jobs"] == []
