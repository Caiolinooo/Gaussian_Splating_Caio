"""Job state machine: enums, legal transitions, resume pointer."""

from __future__ import annotations

from enum import StrEnum
from typing import Never


class JobState(StrEnum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    SFM = "sfm"
    TRAINING = "training"
    EXPORTING = "exporting"
    MESHPROXY = "meshproxy"
    AUTOCAL = "autocal"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceKind(StrEnum):
    VIDEO = "video"
    IMAGES = "images"


STAGE_ORDER: tuple[str, ...] = (
    JobState.EXTRACTING.value,
    JobState.SFM.value,
    JobState.TRAINING.value,
    JobState.EXPORTING.value,
    JobState.MESHPROXY.value,
    JobState.AUTOCAL.value,
)

STAGE_WEIGHTS: dict[str, float] = {
    JobState.EXTRACTING.value: 0.10,
    JobState.SFM.value: 0.18,
    JobState.TRAINING.value: 0.47,
    JobState.EXPORTING.value: 0.10,
    JobState.MESHPROXY.value: 0.05,
    JobState.AUTOCAL.value: 0.10,
}

TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.QUEUED: frozenset({JobState.EXTRACTING, JobState.CANCELLED}),
    JobState.EXTRACTING: frozenset({JobState.SFM, JobState.ERROR, JobState.CANCELLED}),
    JobState.SFM: frozenset({JobState.TRAINING, JobState.ERROR, JobState.CANCELLED}),
    JobState.TRAINING: frozenset({JobState.EXPORTING, JobState.ERROR, JobState.CANCELLED}),
    JobState.EXPORTING: frozenset({JobState.MESHPROXY, JobState.ERROR, JobState.CANCELLED}),
    JobState.MESHPROXY: frozenset({JobState.AUTOCAL, JobState.ERROR, JobState.CANCELLED}),
    JobState.AUTOCAL: frozenset({JobState.DONE, JobState.ERROR, JobState.CANCELLED}),
    JobState.DONE: frozenset(),
    JobState.ERROR: frozenset(
        {
            JobState.QUEUED,
            JobState.EXTRACTING,
            JobState.SFM,
            JobState.TRAINING,
            JobState.EXPORTING,
            JobState.MESHPROXY,
            JobState.AUTOCAL,
        }
    ),
    JobState.CANCELLED: frozenset(
        {
            JobState.QUEUED,
            JobState.EXTRACTING,
            JobState.SFM,
            JobState.TRAINING,
            JobState.EXPORTING,
            JobState.MESHPROXY,
            JobState.AUTOCAL,
        }
    ),
}


def assert_never(value: Never) -> Never:
    raise AssertionError(f"unhandled value: {value!r}")


def can_transition(current: JobState, dest: JobState) -> bool:
    return dest in TRANSITIONS[current]


def next_pipeline_state(current: JobState) -> JobState | None:
    mapping: dict[JobState, JobState | None] = {
        JobState.QUEUED: JobState.EXTRACTING,
        JobState.EXTRACTING: JobState.SFM,
        JobState.SFM: JobState.TRAINING,
        JobState.TRAINING: JobState.EXPORTING,
        JobState.EXPORTING: JobState.MESHPROXY,
        JobState.MESHPROXY: JobState.AUTOCAL,
        JobState.AUTOCAL: JobState.DONE,
        JobState.DONE: None,
        JobState.ERROR: None,
        JobState.CANCELLED: None,
    }
    if current not in mapping:
        assert_never(current)  # type: ignore[arg-type]
    return mapping[current]


def state_to_stage(state: JobState) -> str | None:
    if state.value in STAGE_ORDER:
        return state.value
    return None


def stage_to_state(stage: str) -> JobState:
    return JobState(stage)


def overall_progress(
    stage_statuses: dict[str, StageStatus],
    current_fraction: float,
    current_stage: str | None,
) -> float:
    completed = 0.0
    for name, weight in STAGE_WEIGHTS.items():
        status = stage_statuses.get(name, StageStatus.PENDING)
        if status is StageStatus.DONE or status is StageStatus.SKIPPED:
            completed += weight
            continue
        if name == current_stage and status is StageStatus.RUNNING:
            completed += weight * max(0.0, min(1.0, current_fraction))
    return max(0.0, min(1.0, completed))
