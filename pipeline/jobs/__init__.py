"""Idempotent, resumable pipeline job machine.

Public contract consumed by the FastAPI worker / orchestrator:

* ``JobMachine.create(spec) -> JobRecord``
* ``JobMachine.run(job_id) -> JobRecord``  (blocking; resume-safe)
* ``JobMachine.cancel(job_id)`` / ``JobMachine.retry(job_id)`` / ``JobMachine.get(job_id)``
* ``ProgressSink`` receives ``ProgressEvent`` (WS/SSE-agnostic)
* ``AutocalHook`` is injected; default is ``PipelineAutocal``
* Persisted document: ``JobRecord`` (``schema_version=1``) via ``JsonJobStore`` or ``SqliteJobStore``
"""

from jobs.autocal import AutocalContext, AutocalHook, AutocalResult, NoOpAutocal
from jobs.autocal_adapter import ColmapDepthProvider, PipelineAutocal
from jobs.errors import InvalidTransition, JobError, JobInterrupted, JobNotFound
from jobs.handlers import StageHandlers, StageOutcome, default_handlers
from jobs.machine import JobMachine, apply_transition, resume_stage
from jobs.models import JobRecord, JobSource, JobSpec, StageRecord, ToolPaths
from jobs.paths import JobPaths, job_paths
from jobs.progress import ProgressEvent, ProgressSink
from jobs.runner import CommandResult, CommandRunner, SubprocessRunner
from jobs.states import STAGE_ORDER, JobState, SourceKind, StageStatus, can_transition
from jobs.store import JsonJobStore, SqliteJobStore, record_from_dict, record_to_dict

__all__ = [
    "STAGE_ORDER",
    "AutocalContext",
    "AutocalHook",
    "AutocalResult",
    "CommandResult",
    "CommandRunner",
    "InvalidTransition",
    "JobError",
    "JobInterrupted",
    "JobMachine",
    "JobNotFound",
    "JobPaths",
    "JobRecord",
    "JobSource",
    "JobSpec",
    "JobState",
    "JsonJobStore",
    "ColmapDepthProvider",
    "NoOpAutocal",
    "PipelineAutocal",
    "ProgressEvent",
    "ProgressSink",
    "SourceKind",
    "SqliteJobStore",
    "StageHandlers",
    "StageOutcome",
    "StageRecord",
    "StageStatus",
    "SubprocessRunner",
    "ToolPaths",
    "apply_transition",
    "can_transition",
    "default_handlers",
    "job_paths",
    "record_from_dict",
    "record_to_dict",
    "resume_stage",
]
