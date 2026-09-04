"""Shared fixtures: isolated DATA_ROOT + mocked JobMachine."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.core.config import Settings
from app.main import create_app
from app.services.job_runtime import JobRuntime
from app.services.job_supervisor import JobSupervisor
from app.services.progress_hub import ProgressHub
from app.services.scene_store import SceneStore
from tests.fakes import FakeJobMachine

TEST_JWT_SECRET = "test-supabase-jwt-secret-32chars!"


def build_fake_runtime(settings: Settings, machine: FakeJobMachine | None = None) -> JobRuntime:
    hub = ProgressHub()
    fake = machine or FakeJobMachine(hub)
    fake.hub = hub
    supervisor = JobSupervisor(fake, fake, hub)
    return JobRuntime(
        settings=settings,
        machine=fake,
        store=fake,
        hub=hub,
        supervisor=supervisor,
        scenes=SceneStore(settings),
        available=True,
    )


def make_settings(tmp_path: Path, *, dev_auth_bypass: bool = False) -> Settings:
    return Settings(
        data_root=tmp_path / "data",
        supabase_jwt_secret=TEST_JWT_SECRET,
        dev_auth_bypass=dev_auth_bypass,
        pipeline_path=Path("../../pipeline"),
        max_upload_mb=8,
        max_video_duration_s=1200.0,
        min_images=20,
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def runtime(settings: Settings) -> JobRuntime:
    return build_fake_runtime(settings)


@pytest.fixture
def app(settings: Settings, runtime: JobRuntime):
    return create_app(settings_override=settings, runtime=runtime)


@pytest.fixture
def client_as(app) -> Iterator[Callable[[str], TestClient]]:
    def _make(user_id: str) -> TestClient:
        async def _user() -> CurrentUser:
            return CurrentUser(user_id=user_id)

        app.dependency_overrides[get_current_user] = _user
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()
