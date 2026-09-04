"""Wire JobMachine + SQLite store + supervisor, or accept a test double."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.core.config import Settings
from app.core.errors import unavailable
from app.services.job_records import RESUMABLE_STATES, progress_from_event
from app.services.job_supervisor import JobLookupError, JobMachineProtocol, JobStoreProtocol, JobSupervisor
from app.services.progress_hub import ProgressHub
from app.services.scene_store import SceneStore

LOGGER = logging.getLogger("gs.api.runtime")


@dataclass
class JobRuntime:
    settings: Settings
    machine: JobMachineProtocol
    store: JobStoreProtocol
    hub: ProgressHub
    supervisor: JobSupervisor
    scenes: SceneStore
    available: bool = True

    def require(self) -> JobRuntime:
        if not self.available:
            raise unavailable()
        return self

    async def start(self) -> None:
        if self.available:
            await self.supervisor.start()
        else:
            self.hub.bind_loop(asyncio.get_running_loop())

    async def shutdown(self) -> None:
        if self.available:
            await self.supervisor.shutdown()


class PipelineMachineAdapter:
    """Translate API-side specs into the pipeline ``JobSpec`` / error types."""

    def __init__(self, inner: Any, jobs: Any) -> None:
        self._inner = inner
        self._jobs = jobs

    def _spec(self, spec: Any) -> Any:
        kind = spec.source_kind
        if hasattr(kind, "value"):
            kind_value = kind.value
        else:
            kind_value = str(kind)
        tools = getattr(spec, "tools", None)
        tool_kwargs: dict[str, str] = {}
        if tools is not None:
            for name in ("ffmpeg", "ffprobe", "colmap", "python", "simple_trainer", "splat_transform"):
                value = getattr(tools, name, None)
                if value is not None:
                    tool_kwargs[name] = str(value)
        return self._jobs.JobSpec(
            user_id=str(spec.user_id),
            source_kind=self._jobs.SourceKind(kind_value),
            source_paths=tuple(Path(item) for item in spec.source_paths),
            user_height_m=float(spec.user_height_m),
            work_root=Path(spec.work_root),
            idempotency_key=getattr(spec, "idempotency_key", None),
            tools=self._jobs.ToolPaths(**tool_kwargs) if tool_kwargs else self._jobs.ToolPaths(),
        )

    def _wrap_lookup(self, job_id: str, fn: Any) -> Any:
        try:
            return fn(job_id)
        except self._jobs.JobNotFound as exc:
            raise JobLookupError(job_id) from exc

    def create(self, spec: Any, *, job_id: str | None = None) -> Any:
        return self._inner.create(self._spec(spec), job_id=job_id)

    def run(self, job_id: str) -> Any:
        return self._wrap_lookup(job_id, self._inner.run)

    def cancel(self, job_id: str) -> Any:
        return self._wrap_lookup(job_id, self._inner.cancel)

    def retry(self, job_id: str) -> Any:
        return self._wrap_lookup(job_id, self._inner.retry)

    def get(self, job_id: str) -> Any:
        return self._wrap_lookup(job_id, self._inner.get)


class SqliteStoreAdapter:
    """``list_resumable`` is API-owned — the pipeline store has no list-all API."""

    def __init__(self, store: Any, path: Path, jobs: Any) -> None:
        self._store = store
        self._path = path
        self._jobs = jobs

    def list_by_user(self, user_id: str) -> list[Any]:
        return self._store.list_by_user(user_id)

    def list_resumable(self) -> list[Any]:
        if not self._path.is_file():
            return []
        placeholders = ",".join("?" for _ in RESUMABLE_STATES)
        states = tuple(RESUMABLE_STATES)
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute(
                f"SELECT payload FROM jobs WHERE state IN ({placeholders})",  # noqa: S608 — states are a fixed enum
                states,
            ).fetchall()
        records: list[Any] = []
        for (payload,) in rows:
            try:
                records.append(self._jobs.record_from_dict(json.loads(payload)))
            except Exception:  # noqa: BLE001
                LOGGER.exception("Skipping unreadable job payload during resume")
        return records

    def delete(self, job_id: str) -> Any:
        return self._store.delete(job_id)


def tool_paths_from_settings(settings: Settings) -> Any:
    return SimpleNamespace(
        ffmpeg=settings.tool_ffmpeg,
        ffprobe=settings.tool_ffprobe,
        colmap=settings.tool_colmap,
        python=settings.tool_python,
        simple_trainer=settings.tool_simple_trainer,
        splat_transform=settings.tool_splat_transform,
    )


def build_pipeline_runtime(settings: Settings) -> JobRuntime:
    """Construct the real JobMachine. Deferred import so ``app.main`` stays light."""
    from app.pipeline_jobs import (  # deferred: pipeline must not load at API import
        JobMachine,
        JobNotFound,
        JobSpec,
        SourceKind,
        SqliteJobStore,
        ToolPaths,
        default_handlers,
        record_from_dict,
    )

    jobs_ns = SimpleNamespace(
        JobMachine=JobMachine,
        JobNotFound=JobNotFound,
        JobSpec=JobSpec,
        SourceKind=SourceKind,
        SqliteJobStore=SqliteJobStore,
        ToolPaths=ToolPaths,
        record_from_dict=record_from_dict,
    )

    data_root = settings.resolved_data_root()
    data_root.mkdir(parents=True, exist_ok=True)
    db_path = data_root / "pipeline-jobs.sqlite"
    hub = ProgressHub()

    def sink(event: Any) -> None:
        hub.publish(str(event.job_id), progress_from_event(event))

    store = SqliteJobStore(db_path)
    machine = JobMachine(
        store,
        handlers=default_handlers(),
        progress=sink,
    )
    adapter = PipelineMachineAdapter(machine, jobs_ns)
    store_adapter = SqliteStoreAdapter(store, db_path, jobs_ns)
    supervisor = JobSupervisor(adapter, store_adapter, hub)
    return JobRuntime(
        settings=settings,
        machine=adapter,
        store=store_adapter,
        hub=hub,
        supervisor=supervisor,
        scenes=SceneStore(settings),
        available=True,
    )


def build_unavailable_runtime(settings: Settings) -> JobRuntime:
    class _Down:
        def __getattr__(self, name: str) -> Any:
            raise RuntimeError("pipeline runtime unavailable")

    hub = ProgressHub()
    down = _Down()
    return JobRuntime(
        settings=settings,
        machine=down,  # type: ignore[arg-type]
        store=down,  # type: ignore[arg-type]
        hub=hub,
        supervisor=JobSupervisor(down, down, hub),  # type: ignore[arg-type]
        scenes=SceneStore(settings),
        available=False,
    )


def try_build_pipeline_runtime(settings: Settings) -> JobRuntime:
    try:
        return build_pipeline_runtime(settings)
    except Exception:  # noqa: BLE001 — API must boot even if pipeline is missing
        LOGGER.exception("Pipeline JobMachine is unavailable; job endpoints will return 503")
        return build_unavailable_runtime(settings)
