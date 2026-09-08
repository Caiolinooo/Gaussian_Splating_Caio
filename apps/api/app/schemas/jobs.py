"""Pydantic schemas for job HTTP/WS contracts (snake_case, frontend-facing)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ArtifactKind(StrEnum):
    PLY = "ply"
    KSPLAT = "ksplat"
    THUMBNAIL = "thumbnail"
    LOG = "log"
    SCENE = "scene"
    PACKAGE = "package"


class JobAccepted(BaseModel):
    """POST /jobs and POST /jobs/{id}/retry — 202."""

    job_id: str
    state: str


class JobActionResponse(BaseModel):
    """POST /jobs/{id}/cancel — 200."""

    job_id: str
    state: str


class StageView(BaseModel):
    name: str
    status: str
    progress: float = 0.0
    message: str = ""
    attempt: int = 0
    metrics: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class JobSummary(BaseModel):
    job_id: str
    state: str
    source_kind: str
    user_height_m: float
    created_at: str
    updated_at: str
    overall_progress: float = 0.0
    last_completed_stage: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    idempotency_key: str | None = None


class JobDetail(JobSummary):
    stages: list[StageView] = Field(default_factory=list)
    work_dir: str | None = None


class JobListResponse(BaseModel):
    jobs: list[JobSummary]


class ProgressPayload(BaseModel):
    """WebSocket ``/jobs/{id}/events`` message (mirrors pipeline ProgressEvent)."""

    job_id: str
    state: str
    stage: str | None = None
    stage_progress: float = 0.0
    overall_progress: float = 0.0
    message: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = ""
