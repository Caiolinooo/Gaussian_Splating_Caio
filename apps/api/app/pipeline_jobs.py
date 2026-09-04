# ruff: noqa: I001
"""Typed re-exports of the pipeline job contract.

Imported only when the real ``JobMachine`` is constructed (see
``app.services.job_runtime.build_pipeline_runtime``). Tests never import this
module — they inject a mocked machine.
"""

from __future__ import annotations

import app.pipeline_bridge as _pipeline_bridge  # noqa: F401  — sys.path insert

from jobs import (  # type: ignore[import-not-found]
    JobMachine,
    JobNotFound,
    JobSpec,
    JobState,
    NoOpAutocal,
    ProgressEvent,
    SourceKind,
    SqliteJobStore,
    ToolPaths,
    default_handlers,
)
from jobs.store import record_from_dict  # type: ignore[import-not-found]

__all__ = [
    "JobMachine",
    "JobNotFound",
    "JobSpec",
    "JobState",
    "NoOpAutocal",
    "ProgressEvent",
    "SourceKind",
    "SqliteJobStore",
    "ToolPaths",
    "default_handlers",
    "record_from_dict",
]
