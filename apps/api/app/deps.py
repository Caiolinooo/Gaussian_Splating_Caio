"""FastAPI dependencies: settings, auth, job runtime."""

from __future__ import annotations

from fastapi import Request

from app.core.auth import CurrentUser, get_current_user
from app.core.config import Settings, settings
from app.core.errors import unavailable
from app.services.job_runtime import JobRuntime
from app.services.scene_store import SceneStore

__all__ = ["CurrentUser", "get_current_user", "get_runtime", "get_scene_store", "get_settings"]


def get_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", settings)


def get_runtime(request: Request) -> JobRuntime:
    runtime: JobRuntime | None = getattr(request.app.state, "runtime", None)
    if runtime is None or not runtime.available:
        raise unavailable()
    return runtime


def get_scene_store(request: Request) -> SceneStore:
    runtime: JobRuntime | None = getattr(request.app.state, "runtime", None)
    if runtime is not None:
        return runtime.scenes
    return SceneStore(get_settings(request))
