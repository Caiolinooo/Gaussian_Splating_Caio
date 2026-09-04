"""JSON and SQLite persistence for ``JobRecord`` (schema_version=1)."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from export.config import ExportConfig
from ingest.config import ImageIngestConfig, VideoIngestConfig
from jobs.errors import JobNotFound
from jobs.models import JobRecord, JobSource, StageRecord, ToolPaths
from jobs.states import JobState, SourceKind, StageStatus
from sfm.config import ColmapConfig
from train.config import TrainConfig


class JobStore(Protocol):
    def save(self, record: JobRecord) -> None: ...

    def load(self, job_id: str) -> JobRecord: ...

    def find_by_idempotency(self, user_id: str, key: str) -> JobRecord | None: ...

    def list_by_user(self, user_id: str) -> list[JobRecord]: ...

    def delete(self, job_id: str) -> JobRecord: ...


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: to_jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, frozenset)):
        return [to_jsonable(item) for item in value]
    return value


def record_to_dict(record: JobRecord) -> dict[str, Any]:
    payload = to_jsonable(record)
    if not isinstance(payload, dict):
        raise TypeError("job record serialization failed")
    return payload


def _stage_from_dict(raw: dict[str, Any]) -> StageRecord:
    return StageRecord(
        name=str(raw["name"]),
        status=StageStatus(raw.get("status", "pending")),
        attempt=int(raw.get("attempt", 0)),
        started_at=raw.get("started_at"),
        finished_at=raw.get("finished_at"),
        progress=float(raw.get("progress", 0.0)),
        message=str(raw.get("message", "")),
        artifacts=dict(raw.get("artifacts") or {}),
        metrics=dict(raw.get("metrics") or {}),
        error_code=raw.get("error_code"),
        error_message=raw.get("error_message"),
    )


def _video_ingest(raw: dict[str, Any] | None) -> VideoIngestConfig:
    data = raw or {}
    defaults = VideoIngestConfig()
    return VideoIngestConfig(
        target_min_frames=int(data.get("target_min_frames", defaults.target_min_frames)),
        target_max_frames=int(data.get("target_max_frames", defaults.target_max_frames)),
        oversample=float(data.get("oversample", defaults.oversample)),
        blur_threshold=float(data.get("blur_threshold", defaults.blur_threshold)),
        relaxed_blur_threshold=float(
            data.get("relaxed_blur_threshold", defaults.relaxed_blur_threshold)
        ),
        dedup_threshold=float(data.get("dedup_threshold", defaults.dedup_threshold)),
        max_edge_px=int(data.get("max_edge_px", defaults.max_edge_px)),
        jpeg_quality=int(data.get("jpeg_quality", defaults.jpeg_quality)),
        min_width=int(data.get("min_width", defaults.min_width)),
        min_height=int(data.get("min_height", defaults.min_height)),
        signature_size=int(data.get("signature_size", defaults.signature_size)),
    )


def _image_ingest(raw: dict[str, Any] | None) -> ImageIngestConfig:
    data = raw or {}
    defaults = ImageIngestConfig()
    suffixes = data.get("allowed_suffixes")
    allowed = frozenset(suffixes) if suffixes else defaults.allowed_suffixes
    return ImageIngestConfig(
        min_width=int(data.get("min_width", defaults.min_width)),
        min_height=int(data.get("min_height", defaults.min_height)),
        max_edge_px=int(data.get("max_edge_px", defaults.max_edge_px)),
        allowed_suffixes=allowed,
        normalize_resolution=bool(data.get("normalize_resolution", defaults.normalize_resolution)),
    )


def _colmap(raw: dict[str, Any] | None) -> ColmapConfig:
    data = raw or {}
    defaults = ColmapConfig()
    return ColmapConfig(
        colmap_bin=str(data.get("colmap_bin", defaults.colmap_bin)),
        matcher=data.get("matcher", defaults.matcher),
        camera_model=data.get("camera_model", defaults.camera_model),
        single_camera=bool(data.get("single_camera", defaults.single_camera)),
        use_gpu=bool(data.get("use_gpu", defaults.use_gpu)),
        sequential_overlap=int(data.get("sequential_overlap", defaults.sequential_overlap)),
        sequential_quadratic_overlap=bool(
            data.get("sequential_quadratic_overlap", defaults.sequential_quadratic_overlap)
        ),
        min_registered_ratio=float(data.get("min_registered_ratio", defaults.min_registered_ratio)),
        min_registered_count=int(data.get("min_registered_count", defaults.min_registered_count)),
        timeout_s=data.get("timeout_s", defaults.timeout_s),
    )


def _train(raw: dict[str, Any] | None) -> TrainConfig:
    data = raw or {}
    defaults = TrainConfig()
    return TrainConfig(
        python_bin=str(data.get("python_bin", defaults.python_bin)),
        trainer_script=Path(data.get("trainer_script", defaults.trainer_script)),
        subcommand=str(data.get("subcommand", defaults.subcommand)),
        data_factor=int(data.get("data_factor", defaults.data_factor)),
        max_steps=int(data.get("max_steps", defaults.max_steps)),
        save_steps=tuple(data.get("save_steps", defaults.save_steps)),
        eval_steps=tuple(data.get("eval_steps", defaults.eval_steps)),
        ply_steps=tuple(data.get("ply_steps", defaults.ply_steps)),
        save_ply=bool(data.get("save_ply", defaults.save_ply)),
        disable_viewer=bool(data.get("disable_viewer", defaults.disable_viewer)),
        disable_video=bool(data.get("disable_video", defaults.disable_video)),
        extra_args=tuple(data.get("extra_args", defaults.extra_args)),
        timeout_s=data.get("timeout_s", defaults.timeout_s),
    )


def _export(raw: dict[str, Any] | None) -> ExportConfig:
    data = raw or {}
    defaults = ExportConfig()
    return ExportConfig(
        splat_transform_bin=str(data.get("splat_transform_bin", defaults.splat_transform_bin)),
        ffmpeg_bin=str(data.get("ffmpeg_bin", defaults.ffmpeg_bin)),
        filter_nan=bool(data.get("filter_nan", defaults.filter_nan)),
        filter_floaters=bool(data.get("filter_floaters", defaults.filter_floaters)),
        floater_voxel=float(data.get("floater_voxel", defaults.floater_voxel)),
        floater_opacity=float(data.get("floater_opacity", defaults.floater_opacity)),
        floater_min_contribution=float(
            data.get("floater_min_contribution", defaults.floater_min_contribution)
        ),
        web_sh_degree=data.get("web_sh_degree", defaults.web_sh_degree),
        thumbnail_max_edge=int(data.get("thumbnail_max_edge", defaults.thumbnail_max_edge)),
        thumbnail_name=str(data.get("thumbnail_name", defaults.thumbnail_name)),
        timeout_s=data.get("timeout_s", defaults.timeout_s),
    )


def record_from_dict(data: dict[str, Any]) -> JobRecord:
    raw_source = data.get("source") or {}
    raw_tools = data.get("tools") or {}
    stages_raw = data.get("stages") or {}
    stages = {name: _stage_from_dict(raw) for name, raw in stages_raw.items()}
    return JobRecord(
        schema_version=int(data.get("schema_version", 1)),
        job_id=str(data["job_id"]),
        user_id=str(data["user_id"]),
        state=JobState(data["state"]),
        source=JobSource(
            kind=SourceKind(raw_source.get("kind", "video")),
            paths=list(raw_source.get("paths") or []),
            original_names=list(raw_source.get("original_names") or []),
        ),
        work_dir=str(data["work_dir"]),
        user_height_m=float(data["user_height_m"]),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
        idempotency_key=data.get("idempotency_key"),
        last_completed_stage=data.get("last_completed_stage"),
        cancel_requested=bool(data.get("cancel_requested", False)),
        stages=stages,
        error_code=data.get("error_code"),
        error_message=data.get("error_message"),
        tools=ToolPaths(
            ffmpeg=str(raw_tools.get("ffmpeg", "ffmpeg")),
            ffprobe=str(raw_tools.get("ffprobe", "ffprobe")),
            colmap=str(raw_tools.get("colmap", "colmap")),
            python=str(raw_tools.get("python", "python")),
            simple_trainer=str(raw_tools.get("simple_trainer", "simple_trainer.py")),
            splat_transform=str(raw_tools.get("splat_transform", "splat-transform")),
        ),
        video_ingest=_video_ingest(data.get("video_ingest")),
        image_ingest=_image_ingest(data.get("image_ingest")),
        colmap=_colmap(data.get("colmap")),
        train=_train(data.get("train")),
        export=_export(data.get("export")),
        extra=dict(data.get("extra") or {}),
    )


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


class JsonJobStore:
    """One ``{job_id}.json`` plus ``index.json`` for idempotency keys."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _job_path(self, job_id: str) -> Path:
        return self.directory / f"{job_id}.json"

    def _index_path(self) -> Path:
        return self.directory / "index.json"

    def _read_index(self) -> dict[str, str]:
        path = self._index_path()
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return dict(payload) if isinstance(payload, dict) else {}

    def save(self, record: JobRecord) -> None:
        with self._lock:
            _atomic_write(
                self._job_path(record.job_id),
                json.dumps(record_to_dict(record), indent=2, ensure_ascii=False),
            )
            if record.idempotency_key:
                index = self._read_index()
                index[f"{record.user_id}::{record.idempotency_key}"] = record.job_id
                _atomic_write(self._index_path(), json.dumps(index, indent=2))

    def load(self, job_id: str) -> JobRecord:
        path = self._job_path(job_id)
        if not path.is_file():
            raise JobNotFound(job_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise JobNotFound(job_id)
        return record_from_dict(payload)

    def find_by_idempotency(self, user_id: str, key: str) -> JobRecord | None:
        index = self._read_index()
        job_id = index.get(f"{user_id}::{key}")
        if not job_id:
            return None
        try:
            return self.load(job_id)
        except JobNotFound:
            return None

    def list_by_user(self, user_id: str) -> list[JobRecord]:
        records: list[JobRecord] = []
        for path in self.directory.glob("*.json"):
            if path.name == "index.json":
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("user_id") == user_id:
                records.append(record_from_dict(payload))
        return records

    def delete(self, job_id: str) -> JobRecord:
        with self._lock:
            path = self._job_path(job_id)
            if not path.is_file():
                raise JobNotFound(job_id)
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise JobNotFound(job_id)
            record = record_from_dict(payload)
            path.unlink(missing_ok=True)
            if record.idempotency_key:
                index = self._read_index()
                index.pop(f"{record.user_id}::{record.idempotency_key}", None)
                _atomic_write(self._index_path(), json.dumps(index, indent=2))
            return record


class SqliteJobStore:
    """SQLite source of truth; payload column stores the same JSON document."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    idempotency_key TEXT,
                    state TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS jobs_idempotency
                ON jobs(user_id, idempotency_key)
                WHERE idempotency_key IS NOT NULL
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, record: JobRecord) -> None:
        payload = json.dumps(record_to_dict(record), ensure_ascii=False)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, user_id, idempotency_key, state, payload, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    idempotency_key=excluded.idempotency_key,
                    state=excluded.state,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (
                    record.job_id,
                    record.user_id,
                    record.idempotency_key,
                    record.state.value,
                    payload,
                    record.updated_at,
                ),
            )
            conn.commit()

    def load(self, job_id: str) -> JobRecord:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT payload FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFound(job_id)
        return record_from_dict(json.loads(row["payload"]))

    def find_by_idempotency(self, user_id: str, key: str) -> JobRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM jobs WHERE user_id = ? AND idempotency_key = ?",
                (user_id, key),
            ).fetchone()
        if row is None:
            return None
        return record_from_dict(json.loads(row["payload"]))

    def list_by_user(self, user_id: str) -> list[JobRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM jobs WHERE user_id = ? ORDER BY updated_at",
                (user_id,),
            ).fetchall()
        return [record_from_dict(json.loads(row["payload"])) for row in rows]

    def delete(self, job_id: str) -> JobRecord:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT payload FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise JobNotFound(job_id)
            record = record_from_dict(json.loads(row["payload"]))
            conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            conn.commit()
        return record
