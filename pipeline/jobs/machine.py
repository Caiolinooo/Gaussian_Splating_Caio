"""Idempotent, resumable job state machine.

States: queued → extracting → sfm → training → exporting → autocal → done|error
(plus cancelled). Persistence is store-agnostic (JSON or SQLite).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from jobs.errors import InvalidTransition, JobCancelled, JobInterrupted
from jobs.handlers import StageHandlers, StageOutcome, default_handlers
from jobs.models import JobRecord, JobSpec, new_job_record, utcnow
from jobs.progress import ProgressEvent, ProgressSink, make_event
from jobs.quality import apply_quality_defaults
from jobs.states import (
    STAGE_ORDER,
    JobState,
    StageStatus,
    can_transition,
    next_pipeline_state,
    stage_to_state,
)
from jobs.store import JobStore
from provisioner.bins import resolve_python_bin
from sfm.errors import COLMAP_MISSING_USER

LOGGER = logging.getLogger("pipeline.jobs")


def _looks_like_missing_executable(exc: BaseException) -> bool:
    if isinstance(exc, FileNotFoundError):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in {2, 3}:
        return True
    return getattr(exc, "winerror", None) == 2


def classify_stage_error(stage_name: str, exc: BaseException) -> tuple[str, str]:
    """Preserve coded pipeline errors; map a missing COLMAP binary to COLMAP_FAILED."""
    user_message = getattr(exc, "user_message", None)
    code = getattr(exc, "code", None)
    if isinstance(code, str) and isinstance(user_message, str) and user_message.strip():
        return code, user_message
    if isinstance(code, str):
        fallback = user_message if isinstance(user_message, str) and user_message.strip() else str(exc)
        return code, fallback
    text = f"{exc} {getattr(exc, 'filename', '')}".lower()
    if stage_name == "sfm" and (_looks_like_missing_executable(exc) or "colmap" in text):
        return "COLMAP_FAILED", COLMAP_MISSING_USER
    if isinstance(user_message, str) and user_message.strip():
        return "PIPELINE_ERROR", user_message
    return "PIPELINE_ERROR", "Falha inesperada no pipeline."


def resume_stage(record: JobRecord) -> str | None:
    """First stage that is not done/skipped — the resume cursor."""
    if record.state is JobState.DONE:
        return None
    if record.state in {JobState.QUEUED, JobState.ERROR, JobState.CANCELLED}:
        for name in STAGE_ORDER:
            status = record.stages[name].status
            if status is not StageStatus.DONE and status is not StageStatus.SKIPPED:
                return name
        return None
    current = record.state.value
    if current in STAGE_ORDER:
        status = record.stages[current].status
        if status is StageStatus.DONE or status is StageStatus.SKIPPED:
            nxt = next_pipeline_state(record.state)
            if nxt is None or nxt.value not in STAGE_ORDER:
                return None
            return nxt.value
        return current
    return None


def apply_transition(record: JobRecord, dest: JobState) -> None:
    if dest is record.state:
        return
    if not can_transition(record.state, dest):
        raise InvalidTransition(record.state.value, dest.value)
    LOGGER.info(
        "event=job_transition job_id=%s from=%s to=%s",
        record.job_id,
        record.state.value,
        dest.value,
    )
    record.state = dest
    record.updated_at = utcnow().isoformat()


class JobMachine:
    """Worker-side orchestrator. The API calls ``create`` / ``run`` / ``cancel`` / ``retry``."""

    def __init__(
        self,
        store: JobStore,
        handlers: StageHandlers | None = None,
        progress: ProgressSink | None = None,
        should_cancel: Callable[[JobRecord], bool] | None = None,
    ) -> None:
        self.store = store
        self.handlers = handlers or default_handlers()
        self.progress = progress
        self.should_cancel = should_cancel

    def create(self, spec: JobSpec, *, job_id: str | None = None) -> JobRecord:
        if spec.idempotency_key:
            existing = self.store.find_by_idempotency(spec.user_id, spec.idempotency_key)
            if existing is not None:
                LOGGER.info("event=job_reuse job_id=%s key=%s", existing.job_id, spec.idempotency_key)
                return existing
        record = new_job_record(spec, job_id=job_id)
        record.work_path.mkdir(parents=True, exist_ok=True)
        self.store.save(record)
        self._emit(record, stage=None, fraction=0.0, message="Job enfileirado.")
        return record

    def get(self, job_id: str) -> JobRecord:
        return self.store.load(job_id)

    def cancel(self, job_id: str) -> JobRecord:
        record = self.store.load(job_id)
        record.cancel_requested = True
        if record.state is JobState.QUEUED:
            apply_transition(record, JobState.CANCELLED)
        self.store.save(record)
        self._emit(record, stage=None, fraction=0.0, message="Cancelamento solicitado.")
        return record

    def retry(self, job_id: str) -> JobRecord:
        record = self.store.load(job_id)
        if record.state is JobState.DONE:
            return record
        record.cancel_requested = False
        record.error_code = None
        record.error_message = None
        record.tools.python = resolve_python_bin(record.tools.python)
        target = resume_stage(record) or STAGE_ORDER[0]
        stage = record.stages[target]
        if stage.status is StageStatus.FAILED or stage.status is StageStatus.RUNNING:
            stage.status = StageStatus.PENDING
            stage.error_code = None
            stage.error_message = None
            stage.progress = 0.0
        dest = stage_to_state(target)
        if record.state is not dest:
            if can_transition(record.state, dest):
                apply_transition(record, dest)
            else:
                record.state = dest
                record.updated_at = utcnow().isoformat()
        self.store.save(record)
        return record

    def rebuild(self, job_id: str, from_stage: str = "sfm") -> JobRecord:
        """Reabre um job concluído e reaplica defaults de qualidade a partir de ``from_stage``."""
        if from_stage not in STAGE_ORDER:
            raise ValueError(f"etapa inválida para rebuild: {from_stage}")
        record = self.store.load(job_id)
        apply_quality_defaults(record)
        record.cancel_requested = False
        record.error_code = None
        record.error_message = None
        record.tools.python = resolve_python_bin(record.tools.python)
        index = STAGE_ORDER.index(from_stage)
        for name in STAGE_ORDER[index:]:
            stage = record.stages[name]
            stage.status = StageStatus.PENDING
            stage.progress = 0.0
            stage.error_code = None
            stage.error_message = None
            stage.message = ""
            stage.finished_at = None
        record.last_completed_stage = STAGE_ORDER[index - 1] if index else None
        record.state = stage_to_state(from_stage)
        record.updated_at = utcnow().isoformat()
        self.store.save(record)
        return record

    def run(self, job_id: str) -> JobRecord:
        record = self.store.load(job_id)
        if record.state is JobState.DONE:
            self._emit(record, stage=None, fraction=1.0, message="Job já concluído (idempotente).")
            return record
        if self._cancelled(record):
            return self._mark_cancelled(record)

        stage_name = resume_stage(record)
        while stage_name is not None:
            if self._cancelled(record):
                return self._mark_cancelled(record)
            self._begin_stage(record, stage_name)
            try:
                outcome = self.handlers.get(stage_name)(
                    record,
                    self._stage_progress(record, stage_name),
                )
            except JobInterrupted:
                self._persist_interrupted(record, stage_name)
                raise
            except Exception as exc:
                return self._mark_error(record, stage_name, exc)

            self._complete_stage(record, stage_name, outcome)
            nxt = next_pipeline_state(record.state)
            if nxt is JobState.DONE:
                apply_transition(record, JobState.DONE)
                self.store.save(record)
                self._emit(record, stage=None, fraction=1.0, message="Job concluído.")
                return record
            if nxt is not None and nxt.value in STAGE_ORDER:
                apply_transition(record, nxt)
                self.store.save(record)
                stage_name = nxt.value
                continue
            break

        if all(
            record.stages[name].status in {StageStatus.DONE, StageStatus.SKIPPED}
            for name in STAGE_ORDER
        ):
            if record.state is not JobState.DONE and can_transition(record.state, JobState.DONE):
                apply_transition(record, JobState.DONE)
            elif record.state is not JobState.DONE:
                record.state = JobState.DONE
                record.updated_at = utcnow().isoformat()
            self.store.save(record)
        return record

    def _begin_stage(self, record: JobRecord, stage_name: str) -> None:
        dest = stage_to_state(stage_name)
        if record.state is JobState.QUEUED:
            apply_transition(record, dest)
        elif record.state is not dest:
            if can_transition(record.state, dest):
                apply_transition(record, dest)
            else:
                record.state = dest
                record.updated_at = utcnow().isoformat()
        stage = record.stages[stage_name]
        if stage.status is StageStatus.DONE:
            return
        stage.status = StageStatus.RUNNING
        stage.attempt += 1
        stage.started_at = utcnow().isoformat()
        stage.finished_at = None
        stage.progress = 0.0
        stage.error_code = None
        stage.error_message = None
        record.error_code = None
        record.error_message = None
        self.store.save(record)
        self._emit(record, stage=stage_name, fraction=0.0, message=f"Iniciando {stage_name}…")

    def _complete_stage(self, record: JobRecord, stage_name: str, outcome: StageOutcome) -> None:
        stage = record.stages[stage_name]
        stage.status = StageStatus.SKIPPED if outcome.skipped else StageStatus.DONE
        stage.progress = 1.0
        stage.finished_at = utcnow().isoformat()
        stage.message = outcome.message
        stage.artifacts = dict(outcome.artifacts)
        stage.metrics = dict(outcome.metrics)
        record.last_completed_stage = stage_name
        record.updated_at = utcnow().isoformat()
        self.store.save(record)
        self._emit(record, stage=stage_name, fraction=1.0, message=outcome.message, metrics=outcome.metrics)
        LOGGER.info(
            "event=stage_done job_id=%s stage=%s attempt=%s",
            record.job_id,
            stage_name,
            stage.attempt,
        )

    def _persist_interrupted(self, record: JobRecord, stage_name: str) -> None:
        stage = record.stages[stage_name]
        stage.status = StageStatus.RUNNING
        stage.message = "Interrompido — será retomado nesta etapa."
        record.updated_at = utcnow().isoformat()
        self.store.save(record)
        LOGGER.info("event=job_interrupted job_id=%s stage=%s", record.job_id, stage_name)

    def _mark_error(self, record: JobRecord, stage_name: str, exc: BaseException) -> JobRecord:
        error_code, message = classify_stage_error(stage_name, exc)
        stage = record.stages[stage_name]
        stage.status = StageStatus.FAILED
        stage.finished_at = utcnow().isoformat()
        stage.error_code = error_code
        stage.error_message = message
        stage.message = message
        record.error_code = error_code
        record.error_message = message
        if can_transition(record.state, JobState.ERROR):
            apply_transition(record, JobState.ERROR)
        else:
            record.state = JobState.ERROR
            record.updated_at = utcnow().isoformat()
        self.store.save(record)
        self._emit(
            record,
            stage=stage_name,
            fraction=stage.progress,
            message=message,
            metrics={"error_code": error_code},
        )
        LOGGER.info("event=job_error job_id=%s stage=%s code=%s", record.job_id, stage_name, error_code)
        return record

    def _mark_cancelled(self, record: JobRecord) -> JobRecord:
        record.cancel_requested = True
        if can_transition(record.state, JobState.CANCELLED):
            apply_transition(record, JobState.CANCELLED)
        else:
            record.state = JobState.CANCELLED
            record.updated_at = utcnow().isoformat()
        self.store.save(record)
        self._emit(record, stage=None, fraction=0.0, message="Job cancelado.")
        return record

    def _cancelled(self, record: JobRecord) -> bool:
        fresh = self.store.load(record.job_id)
        record.cancel_requested = fresh.cancel_requested
        if record.cancel_requested:
            return True
        if self.should_cancel is not None:
            return self.should_cancel(record)
        return False

    def _stage_progress(self, record: JobRecord, stage_name: str) -> Callable[[float, str], None]:
        def report(fraction: float, message: str) -> None:
            stage = record.stages[stage_name]
            stage.progress = max(0.0, min(1.0, fraction))
            stage.message = message
            record.updated_at = utcnow().isoformat()
            self.store.save(record)
            self._emit(record, stage=stage_name, fraction=stage.progress, message=message)

        return report

    def _emit(
        self,
        record: JobRecord,
        *,
        stage: str | None,
        fraction: float,
        message: str,
        metrics: dict[str, object] | None = None,
    ) -> None:
        if self.progress is None:
            return
        statuses = {name: item.status for name, item in record.stages.items()}
        event: ProgressEvent = make_event(
            job_id=record.job_id,
            state=record.state,
            stages=statuses,
            stage=stage,
            stage_progress=fraction,
            message=message,
            metrics=metrics,
        )
        self.progress(event)


def raise_if_cancelled(record: JobRecord) -> None:
    if record.cancel_requested:
        raise JobCancelled(record.job_id)
