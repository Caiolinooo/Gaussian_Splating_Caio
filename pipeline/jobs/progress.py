"""WebSocket-agnostic progress events. The API layer adapts these to WS/SSE."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from jobs.states import JobState, StageStatus, overall_progress


@dataclass(frozen=True)
class ProgressEvent:
    job_id: str
    state: JobState
    stage: str | None
    stage_progress: float
    overall_progress: float
    message: str
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            object.__setattr__(self, "timestamp", datetime.now(UTC).isoformat())


ProgressSink = Callable[[ProgressEvent], None]


def make_event(
    *,
    job_id: str,
    state: JobState,
    stages: dict[str, StageStatus],
    stage: str | None,
    stage_progress: float,
    message: str,
    metrics: dict[str, Any] | None = None,
) -> ProgressEvent:
    return ProgressEvent(
        job_id=job_id,
        state=state,
        stage=stage,
        stage_progress=stage_progress,
        overall_progress=overall_progress(stages, stage_progress, stage),
        message=message,
        metrics=dict(metrics or {}),
        timestamp=datetime.now(UTC).isoformat(),
    )
