"""Ponto de entrada da API local (``uvicorn app.main:app``)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, settings
from app.routers import health, jobs, scenes, setup
from app.services.job_runtime import JobRuntime, try_build_pipeline_runtime


def create_app(
    *,
    settings_override: Settings | None = None,
    runtime: JobRuntime | None = None,
) -> FastAPI:
    cfg = settings_override or settings

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
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(setup.router)
    app.include_router(jobs.router)
    app.include_router(scenes.router)
    return app


app = create_app()
