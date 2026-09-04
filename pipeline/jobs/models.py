"""Persisted job document (schema_version=1) and create-spec."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from export.config import ExportConfig
from ingest.config import ImageIngestConfig, VideoIngestConfig
from jobs.states import STAGE_ORDER, JobState, SourceKind, StageStatus
from sfm.config import ColmapConfig
from train.config import TrainConfig


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class ToolPaths:
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    colmap: str = "colmap"
    python: str = "python"
    simple_trainer: str = "simple_trainer.py"
    splat_transform: str = "splat-transform"


@dataclass
class JobSource:
    kind: SourceKind
    paths: list[str]
    original_names: list[str] = field(default_factory=list)


@dataclass
class StageRecord:
    name: str
    status: StageStatus = StageStatus.PENDING
    attempt: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    progress: float = 0.0
    message: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None


@dataclass
class JobRecord:
    """On-disk job document. ``schema_version`` is bumped only on breaking changes."""

    job_id: str
    user_id: str
    state: JobState
    source: JobSource
    work_dir: str
    user_height_m: float
    created_at: str
    updated_at: str
    schema_version: int = 1
    idempotency_key: str | None = None
    last_completed_stage: str | None = None
    cancel_requested: bool = False
    stages: dict[str, StageRecord] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    tools: ToolPaths = field(default_factory=ToolPaths)
    video_ingest: VideoIngestConfig = field(default_factory=VideoIngestConfig)
    image_ingest: ImageIngestConfig = field(default_factory=ImageIngestConfig)
    colmap: ColmapConfig = field(default_factory=ColmapConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def work_path(self) -> Path:
        return Path(self.work_dir)


@dataclass(frozen=True)
class JobSpec:
    """API/orchestrator payload to create a job."""

    user_id: str
    source_kind: SourceKind
    source_paths: tuple[Path, ...]
    user_height_m: float
    work_root: Path
    idempotency_key: str | None = None
    tools: ToolPaths = field(default_factory=ToolPaths)
    video_ingest: VideoIngestConfig = field(default_factory=VideoIngestConfig)
    image_ingest: ImageIngestConfig = field(default_factory=ImageIngestConfig)
    colmap: ColmapConfig = field(default_factory=ColmapConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.5 <= self.user_height_m <= 2.8:
            raise ValueError("user_height_m must be between 0.5 and 2.8")
        if not self.source_paths:
            raise ValueError("source_paths must not be empty")
        if not self.user_id:
            raise ValueError("user_id is required")


def empty_stages() -> dict[str, StageRecord]:
    return {name: StageRecord(name=name) for name in STAGE_ORDER}


def new_job_record(spec: JobSpec, *, job_id: str | None = None) -> JobRecord:
    stamp = utcnow().isoformat()
    resolved_id = job_id or str(uuid4())
    work_dir = spec.work_root / spec.user_id / resolved_id
    names = [path.name for path in spec.source_paths]
    return JobRecord(
        job_id=resolved_id,
        user_id=spec.user_id,
        state=JobState.QUEUED,
        source=JobSource(
            kind=spec.source_kind,
            paths=[str(path) for path in spec.source_paths],
            original_names=names,
        ),
        work_dir=str(work_dir),
        user_height_m=spec.user_height_m,
        created_at=stamp,
        updated_at=stamp,
        idempotency_key=spec.idempotency_key,
        stages=empty_stages(),
        tools=spec.tools,
        video_ingest=spec.video_ingest,
        image_ingest=spec.image_ingest,
        colmap=spec.colmap,
        train=spec.train,
        export=spec.export,
        extra=dict(spec.extra),
    )
