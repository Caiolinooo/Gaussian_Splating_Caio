"""Adapt pipeline ``JobRecord`` (or a test double) into API schemas."""

from __future__ import annotations

from typing import Any

from app.schemas.jobs import JobDetail, JobSummary, ProgressPayload, StageView

STAGE_ORDER: tuple[str, ...] = (
    "extracting",
    "sfm",
    "training",
    "exporting",
    "meshproxy",
    "autocal",
)
STAGE_WEIGHTS: dict[str, float] = {
    "extracting": 0.10,
    "sfm": 0.18,
    "training": 0.47,
    "exporting": 0.10,
    "meshproxy": 0.05,
    "autocal": 0.10,
}
RESUMABLE_STATES: frozenset[str] = frozenset(
    {"queued", "extracting", "sfm", "training", "exporting", "meshproxy", "autocal"}
)
TERMINAL_STATES: frozenset[str] = frozenset({"done", "error", "cancelled"})
RETRYABLE_STATES: frozenset[str] = frozenset({"error", "cancelled"})


def enum_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def record_user_id(record: Any) -> str:
    return str(record.user_id)


def overall_progress(record: Any) -> float:
    stages = getattr(record, "stages", {}) or {}
    completed = 0.0
    for name, weight in STAGE_WEIGHTS.items():
        stage = stages.get(name)
        if stage is None:
            continue
        status = enum_value(getattr(stage, "status", "pending"))
        if status in {"done", "skipped"}:
            completed += weight
        elif status == "running":
            completed += weight * max(0.0, min(1.0, float(getattr(stage, "progress", 0.0))))
    return max(0.0, min(1.0, completed))


def _running_stage(record: Any) -> tuple[str | None, float]:
    stages = getattr(record, "stages", {}) or {}
    for name in STAGE_ORDER:
        stage = stages.get(name)
        if stage is None:
            continue
        if enum_value(getattr(stage, "status", "")) == "running":
            return name, float(getattr(stage, "progress", 0.0))
    return None, 0.0


def _latest_message(record: Any) -> str:
    err = getattr(record, "error_message", None)
    if isinstance(err, str) and err:
        return err
    stages = getattr(record, "stages", {}) or {}
    current, _ = _running_stage(record)
    if current and current in stages:
        message = getattr(stages[current], "message", "")
        if message:
            return str(message)
    last = getattr(record, "last_completed_stage", None)
    if last and last in stages:
        message = getattr(stages[last], "message", "")
        if message:
            return str(message)
    return ""


def _source_kind(record: Any) -> str:
    source = getattr(record, "source", None)
    if source is None:
        return "video"
    return enum_value(getattr(source, "kind", "video"))


def stage_views(record: Any) -> list[StageView]:
    stages = getattr(record, "stages", {}) or {}
    views: list[StageView] = []
    names = list(STAGE_ORDER)
    for name in stages:
        if name not in names:
            names.append(name)
    for name in names:
        stage = stages.get(name)
        if stage is None:
            views.append(StageView(name=name, status="pending"))
            continue
        views.append(
            StageView(
                name=name,
                status=enum_value(getattr(stage, "status", "pending")),
                progress=float(getattr(stage, "progress", 0.0)),
                message=str(getattr(stage, "message", "") or ""),
                attempt=int(getattr(stage, "attempt", 0) or 0),
                metrics=dict(getattr(stage, "metrics", None) or {}),
                error_code=getattr(stage, "error_code", None),
                error_message=getattr(stage, "error_message", None),
                started_at=getattr(stage, "started_at", None),
                finished_at=getattr(stage, "finished_at", None),
            )
        )
    return views


def to_summary(record: Any) -> JobSummary:
    return JobSummary(
        job_id=str(record.job_id),
        state=enum_value(record.state),
        source_kind=_source_kind(record),
        user_height_m=float(record.user_height_m),
        created_at=str(record.created_at),
        updated_at=str(record.updated_at),
        overall_progress=overall_progress(record),
        last_completed_stage=getattr(record, "last_completed_stage", None),
        error_code=getattr(record, "error_code", None),
        error_message=getattr(record, "error_message", None),
        idempotency_key=getattr(record, "idempotency_key", None),
    )


def to_detail(record: Any) -> JobDetail:
    summary = to_summary(record)
    return JobDetail(
        **summary.model_dump(),
        stages=stage_views(record),
        work_dir=str(getattr(record, "work_dir", "") or ""),
    )


def snapshot_payload(record: Any) -> ProgressPayload:
    stage, fraction = _running_stage(record)
    error_code = getattr(record, "error_code", None)
    metrics: dict[str, Any] = {}
    if isinstance(error_code, str) and error_code:
        metrics["error_code"] = error_code
    return ProgressPayload(
        job_id=str(record.job_id),
        state=enum_value(record.state),
        stage=stage,
        stage_progress=fraction,
        overall_progress=overall_progress(record),
        message=_latest_message(record),
        metrics=metrics,
        timestamp=str(getattr(record, "updated_at", "") or ""),
    )


def progress_from_event(event: Any) -> ProgressPayload:
    metrics = getattr(event, "metrics", None) or {}
    return ProgressPayload(
        job_id=str(event.job_id),
        state=enum_value(event.state),
        stage=getattr(event, "stage", None),
        stage_progress=float(getattr(event, "stage_progress", 0.0) or 0.0),
        overall_progress=float(getattr(event, "overall_progress", 0.0) or 0.0),
        message=str(getattr(event, "message", "") or ""),
        metrics=dict(metrics),
        timestamp=str(getattr(event, "timestamp", "") or ""),
    )
