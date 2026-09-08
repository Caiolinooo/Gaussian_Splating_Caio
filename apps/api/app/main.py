"""Ponto de entrada da API local (``uvicorn app.main:app``)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import Settings, settings
from app.routers import auth, health, jobs, scenes, setup
from app.services.job_runtime import JobRuntime, try_build_pipeline_runtime


def _mount_web_spa(app: FastAPI, web_dir: Path) -> None:
    """Serve the Vite build on the same origin as the API (eval / porta única)."""
    assets = web_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

    index = web_dir / "index.html"

    @app.get("/")
    async def web_index() -> FileResponse:
        return FileResponse(index)

    @app.get("/{full_path:path}")
    async def web_spa(full_path: str) -> FileResponse:
        candidate = (web_dir / full_path).resolve()
        try:
            candidate.relative_to(web_dir.resolve())
        except ValueError:
            return FileResponse(index)
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


def create_app(
    *,
    settings_override: Settings | None = None,
    runtime: JobRuntime | None = None,
) -> FastAPI:
    cfg = settings_override or settings
    allow_all = cfg.cors_origins == ["*"]

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = cfg
        if runtime is not None:
            app.state.runtime = runtime
        else:
            app.state.runtime = try_build_pipeline_runtime(cfg)
        await app.state.runtime.start()
        try:
            yield
        finally:
            await app.state.runtime.shutdown()

    app = FastAPI(title=cfg.app_name, version=cfg.version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else cfg.cors_origins,
        allow_credentials=not allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(setup.router)
    app.include_router(auth.router)
    app.include_router(jobs.router)
    app.include_router(scenes.router)
    web_dir = cfg.resolved_serve_web_dir()
    if web_dir is not None:
        _mount_web_spa(app, web_dir)
    return app


app = create_app()
