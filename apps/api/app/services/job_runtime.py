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
        spec_kwargs: dict[str, Any] = {
            "user_id": str(spec.user_id),
            "source_kind": self._jobs.SourceKind(kind_value),
            "source_paths": tuple(Path(item) for item in spec.source_paths),
            "user_height_m": float(spec.user_height_m),
            "work_root": Path(spec.work_root),
            "idempotency_key": getattr(spec, "idempotency_key", None),
            "tools": self._jobs.ToolPaths(**tool_kwargs) if tool_kwargs else self._jobs.ToolPaths(),
        }
        train = getattr(spec, "train", None)
        if train is not None and hasattr(self._jobs, "TrainConfig"):
            spec_kwargs["train"] = self._jobs.TrainConfig(
                python_bin=tool_kwargs.get("python", "python"),
                trainer_script=Path(tool_kwargs.get("simple_trainer", "simple_trainer.py")),
                data_factor=int(getattr(train, "data_factor", 4)),
                max_steps=int(getattr(train, "max_steps", 3500)),
                save_steps=tuple(getattr(train, "save_steps", (3500,))),
                eval_steps=tuple(getattr(train, "eval_steps", (3500,))),
                ply_steps=tuple(getattr(train, "ply_steps", (3500,))),
                extra_args=tuple(getattr(train, "extra_args", ())),
            )
        colmap = getattr(spec, "colmap", None)
        if colmap is not None and hasattr(self._jobs, "ColmapConfig"):
            spec_kwargs["colmap"] = self._jobs.ColmapConfig(
                colmap_bin=tool_kwargs.get("colmap", "colmap"),
                matcher=getattr(colmap, "matcher", "auto"),
                use_gpu=bool(getattr(colmap, "use_gpu", True)),
                min_registered_ratio=float(getattr(colmap, "min_registered_ratio", 0.70)),
                min_registered_count=int(getattr(colmap, "min_registered_count", 20)),
                max_exhaustive_images=int(getattr(colmap, "max_exhaustive_images", 80)),
            )
        return self._jobs.JobSpec(**spec_kwargs)

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
    from provisioner.bins import (
        resolve_colmap_bin,
        resolve_ffmpeg_bin,
        resolve_ffprobe_bin,
        resolve_python_bin,
        resolve_simple_trainer,
        resolve_splat_transform,
    )

    colmap = resolve_colmap_bin(settings.tool_colmap) or settings.tool_colmap
    return SimpleNamespace(
        ffmpeg=resolve_ffmpeg_bin(settings.tool_ffmpeg),
        ffprobe=resolve_ffprobe_bin(settings.tool_ffprobe),
        colmap=colmap,
        python=resolve_python_bin(settings.tool_python),
        simple_trainer=resolve_simple_trainer(settings.tool_simple_trainer),
        splat_transform=resolve_splat_transform(settings.tool_splat_transform),
    )


def train_from_settings(settings: Settings) -> Any:
    steps = int(settings.train_max_steps)
    degree = int(settings.train_sh_degree)
    return SimpleNamespace(
        data_factor=int(settings.train_data_factor),
        max_steps=steps,
        save_steps=(steps,),
        eval_steps=(steps,),
        ply_steps=(steps,),
        extra_args=("--sh_degree", str(degree)),
    )


def colmap_from_settings(settings: Settings) -> Any:
    return SimpleNamespace(
        matcher="auto",
        use_gpu=bool(settings.colmap_use_gpu),
        min_registered_ratio=float(settings.colmap_min_registered_ratio),
        min_registered_count=int(settings.colmap_min_registered_count),
        max_exhaustive_images=int(settings.colmap_max_exhaustive_images),
    )


def build_pipeline_runtime(settings: Settings) -> JobRuntime:
    """Construct the real JobMachine. Deferred import so ``app.main`` stays light."""
    from app.pipeline_jobs import (  # deferred: pipeline must not load at API import
        ColmapConfig,
        JobMachine,
        JobNotFound,
        JobSpec,
        SourceKind,
        SqliteJobStore,
        ToolPaths,
        TrainConfig,
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
        ColmapConfig=ColmapConfig,
        TrainConfig=TrainConfig,
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
