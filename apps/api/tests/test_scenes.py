"""Scene GET/PUT with optimistic version conflict and user isolation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user


def _scene_body(name: str = "Sala", version: int = 1) -> dict[str, object]:
    return {
        "schema_version": 1,
        "version": version,
        "id": "sala",
        "name": name,
        "job_id": None,
        "background_splat": None,
        "nodes": [],
        "calibration": {"scale_factor": None, "source": "none", "confidence": None},
        "overlays": [],
    }


def test_put_get_scene(client_as) -> None:
    with client_as("user-a") as client:
        created = client.put("/scenes/sala", json=_scene_body())
        assert created.status_code == 200
        assert created.json()["version"] == 1
        fetched = client.get("/scenes/sala")
        assert fetched.status_code == 200
        assert fetched.json()["name"] == "Sala"


def test_put_scene_version_conflict(client_as) -> None:
    with client_as("user-a") as client:
        first = client.put("/scenes/sala", json=_scene_body())
        assert first.status_code == 200
        second = client.put("/scenes/sala", json=_scene_body(name="Sala 2", version=1))
        assert second.status_code == 200
        assert second.json()["version"] == 2
        stale = client.put("/scenes/sala", json=_scene_body(name="Sala 3", version=1))
        assert stale.status_code == 409
        detail = stale.json()["detail"]
        assert detail["code"] == "VERSION_CONFLICT"
        assert detail["current_version"] == 2


def test_scene_isolation_between_users(client_as, app) -> None:
    with client_as("user-a") as client:
        assert client.put("/scenes/sala", json=_scene_body()).status_code == 200

    async def _user_b() -> CurrentUser:
        return CurrentUser(user_id="user-b")

    app.dependency_overrides[get_current_user] = _user_b
    with TestClient(app) as client_b:
        missing = client_b.get("/scenes/sala")
        assert missing.status_code == 404
        created = client_b.put("/scenes/sala", json=_scene_body(name="Sala B"))
        assert created.status_code == 200

    async def _user_a() -> CurrentUser:
        return CurrentUser(user_id="user-a")

    app.dependency_overrides[get_current_user] = _user_a
    with TestClient(app) as client_a:
        own = client_a.get("/scenes/sala")
        assert own.status_code == 200
        assert own.json()["name"] == "Sala"


def test_scene_rejects_traversal_id(client_as) -> None:
    with client_as("user-a") as client:
        response = client.get("/scenes/..%2F..%2Fsecret")
    assert response.status_code in {404, 422}
