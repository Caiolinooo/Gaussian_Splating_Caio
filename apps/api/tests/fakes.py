"""In-memory JobMachine/store used by API tests (never imports ``pipeline/``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.job_records import STAGE_ORDER, snapshot_payload
from app.services.job_supervisor import JobLookupError
from app.services.progress_hub import ProgressHub


def _utc() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class FakeStage:
    name: str
    status: str = "pending"
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
class FakeSource:
    kind: str
    paths: list[str]
    original_names: list[str] = field(default_factory=list)


@dataclass
class FakeRecord:
    job_id: str
    user_id: str
    state: str
    source: FakeSource
    work_dir: str
    user_height_m: float
    created_at: str
    updated_at: str
    idempotency_key: str | None = None
    last_completed_stage: str | None = None
    cancel_requested: bool = False
    stages: dict[str, FakeStage] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None

    @property
    def work_path(self) -> Path:
        return Path(self.work_dir)


class FakeJobMachine:
    def __init__(self, hub: ProgressHub | None = None) -> None:
        self.jobs: dict[str, FakeRecord] = {}
        self.hub = hub
        self.block_run: Any = None
        self.run_calls: list[str] = []

    def _emit(self, record: FakeRecord, stage: str | None, fraction: float, message: str) -> None:
        if self.hub is None:
            return
        payload = snapshot_payload(record)
        payload = payload.model_copy(
            update={
                "stage": stage,
                "stage_progress": fraction,
                "message": message,
                "timestamp": record.updated_at,
            }
        )
        self.hub.publish(record.job_id, payload)

    def create(self, spec: Any, *, job_id: str | None = None) -> FakeRecord:
        key = getattr(spec, "idempotency_key", None)
        if key:
            for record in self.jobs.values():
                if record.user_id == spec.user_id and record.idempotency_key == key:
                    return record
        resolved_id = job_id or str(uuid4())
        work_dir = Path(spec.work_root) / spec.user_id / resolved_id
        work_dir.mkdir(parents=True, exist_ok=True)
        stamp = _utc()
        kind = spec.source_kind.value if hasattr(spec.source_kind, "value") else str(spec.source_kind)
        record = FakeRecord(
            job_id=resolved_id,
            user_id=str(spec.user_id),
            state="queued",
            source=FakeSource(
                kind=kind,
                paths=[str(path) for path in spec.source_paths],
                original_names=[Path(str(path)).name for path in spec.source_paths],
            ),
            work_dir=str(work_dir),
            user_height_m=float(spec.user_height_m),
            created_at=stamp,
            updated_at=stamp,
            idempotency_key=key,
            stages={name: FakeStage(name=name) for name in STAGE_ORDER},
        )
        self.jobs[resolved_id] = record
        self._emit(record, None, 0.0, "Job enfileirado.")
        return record

    def get(self, job_id: str) -> FakeRecord:
        try:
            return self.jobs[job_id]
        except KeyError as exc:
            raise JobLookupError(job_id) from exc

    def list_by_user(self, user_id: str) -> list[FakeRecord]:
        return [record for record in self.jobs.values() if record.user_id == user_id]

    def list_resumable(self) -> list[FakeRecord]:
        resumable = {"queued", "extracting", "sfm", "training", "exporting", "meshproxy", "autocal"}
        return [record for record in self.jobs.values() if record.state in resumable]

    def delete(self, job_id: str) -> FakeRecord:
        record = self.get(job_id)
        del self.jobs[job_id]
        return record

    def cancel(self, job_id: str) -> FakeRecord:
        record = self.get(job_id)
        record.cancel_requested = True
        if record.state == "queued":
            record.state = "cancelled"
        record.updated_at = _utc()
        self._emit(record, None, 0.0, "Cancelamento solicitado.")
        return record

    def rebuild(self, job_id: str, from_stage: str = "sfm") -> FakeRecord:
        record = self.get(job_id)
        record.cancel_requested = False
        record.error_code = None
        record.error_message = None
        record.state = from_stage
        reset = False
        for name, stage in record.stages.items():
            if name == from_stage:
                reset = True
            if reset:
                stage.status = "pending"
                stage.progress = 0.0
                stage.error_code = None
                stage.error_message = None
        record.updated_at = _utc()
        return record

    def retry(self, job_id: str) -> FakeRecord:
        record = self.get(job_id)
        if record.state == "done":
            return record
        record.cancel_requested = False
        record.error_code = None
        record.error_message = None
        record.state = "queued"
        for stage in record.stages.values():
            if stage.status in {"failed", "running"}:
                stage.status = "pending"
                stage.error_code = None
                stage.error_message = None
                stage.progress = 0.0
        record.updated_at = _utc()
        return record

    def run(self, job_id: str) -> FakeRecord:
        self.run_calls.append(job_id)
        record = self.get(job_id)
        if self.block_run is not None:
            self.block_run.wait(timeout=5)
        if record.state == "done":
            self._emit(record, None, 1.0, "Job já concluído (idempotente).")
            return record
        if record.cancel_requested:
            record.state = "cancelled"
            record.updated_at = _utc()
            self._emit(record, None, 0.0, "Job cancelado.")
            return record
        for name in STAGE_ORDER:
            if record.cancel_requested:
                record.state = "cancelled"
                record.updated_at = _utc()
                self._emit(record, None, 0.0, "Job cancelado.")
                return record
            record.state = name
            stage = record.stages[name]
            stage.status = "running"
            stage.attempt += 1
            stage.started_at = _utc()
            stage.progress = 0.5
            stage.message = f"Iniciando {name}…"
            record.updated_at = _utc()
            self._emit(record, name, 0.5, stage.message)
            stage.status = "done"
            stage.progress = 1.0
            stage.finished_at = _utc()
            stage.message = f"{name} concluído."
            record.last_completed_stage = name
            record.updated_at = _utc()
            self._emit(record, name, 1.0, stage.message)
        record.state = "done"
        record.updated_at = _utc()
        self._emit(record, None, 1.0, "Job concluído.")
        return record
