"""Job upload, status, cancel/retry, artifacts and progress WebSocket."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse

from app.core.auth import CurrentUser, authenticate_websocket, get_current_user
from app.core.errors import forbidden, not_found, unprocessable
from app.deps import get_runtime
from app.schemas.jobs import (
    ArtifactKind,
    JobAccepted,
    JobActionResponse,
    JobDetail,
    JobListResponse,
    ProgressPayload,
)
from app.services.artifact_service import media_type_for, resolve_artifact
from app.services.job_records import (
    RETRYABLE_STATES,
    TERMINAL_STATES,
    enum_value,
    snapshot_payload,
    to_detail,
    to_summary,
)
from app.services.job_runtime import JobRuntime, tool_paths_from_settings
from app.services.job_supervisor import JobLookupError
from app.services.upload_service import parse_user_height_m, require_idempotency_key, save_uploads

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _require_owner(record: object, user: CurrentUser) -> None:
    if str(getattr(record, "user_id", "")) != user.user_id:
        raise forbidden()


def _load_owned(runtime: JobRuntime, job_id: str, user: CurrentUser) -> object:
    try:
        record = runtime.machine.get(job_id)
    except JobLookupError as exc:
        raise not_found("Job não encontrado.", "JOB_NOT_FOUND") from exc
    _require_owner(record, user)
    return record


def _sse_frame(payload: ProgressPayload) -> str:
    return f"data: {json.dumps(payload.model_dump(), ensure_ascii=False)}\n\n"


async def _iter_progress(runtime: JobRuntime, job_id: str, record: object) -> AsyncIterator[ProgressPayload]:
    snapshot: ProgressPayload = runtime.hub.latest(job_id) or snapshot_payload(record)
    yield snapshot
    if snapshot.state in TERMINAL_STATES:
        return
    async for event in runtime.hub.subscribe(job_id):
        yield event
        if event.state in TERMINAL_STATES:
            return


@router.post("", status_code=202, response_model=JobAccepted)
async def create_job(
    user_height_m: str = Form(...),
    idempotency_key: str = Form(...),
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    files_bracket: list[UploadFile] | None = File(default=None, alias="files[]"),
    user: CurrentUser = Depends(get_current_user),
    runtime: JobRuntime = Depends(get_runtime),
) -> JobAccepted:
    height = parse_user_height_m(user_height_m)
    key = require_idempotency_key(idempotency_key)
    images = list(files or []) + list(files_bracket or [])
    job_id = str(uuid4())
    saved = await save_uploads(
        settings=runtime.settings,
        user_id=user.user_id,
        job_id=job_id,
        video=file,
        images=images,
    )
    spec = SimpleNamespace(
        user_id=user.user_id,
        source_kind=saved.source_kind,
        source_paths=saved.paths,
        user_height_m=height,
        work_root=runtime.settings.resolved_data_root(),
        idempotency_key=key,
        tools=tool_paths_from_settings(runtime.settings),
    )
    try:
        record = runtime.machine.create(spec, job_id=job_id)
    except ValueError as exc:
        raise unprocessable(str(exc) or "Não foi possível criar o job.", "INVALID_JOB_SPEC") from exc
    runtime.supervisor.dispatch(str(record.job_id))
    return JobAccepted(job_id=str(record.job_id), state=enum_value(record.state))


@router.get("", response_model=JobListResponse)
def list_jobs(
    user: CurrentUser = Depends(get_current_user),
    runtime: JobRuntime = Depends(get_runtime),
) -> JobListResponse:
    records = runtime.store.list_by_user(user.user_id)
    summaries = sorted((to_summary(item) for item in records), key=lambda item: item.updated_at, reverse=True)
    return JobListResponse(jobs=summaries)


@router.get("/{job_id}", response_model=JobDetail)
def get_job(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
    runtime: JobRuntime = Depends(get_runtime),
) -> JobDetail:
    return to_detail(_load_owned(runtime, job_id, user))


@router.post("/{job_id}/cancel", response_model=JobActionResponse)
def cancel_job(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
    runtime: JobRuntime = Depends(get_runtime),
) -> JobActionResponse:
    _load_owned(runtime, job_id, user)
    record = runtime.supervisor.cancel(job_id)
    return JobActionResponse(job_id=str(record.job_id), state=enum_value(record.state))


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
    runtime: JobRuntime = Depends(get_runtime),
) -> Response:
    _load_owned(runtime, job_id, user)
    runtime.supervisor.delete(job_id)
    return Response(status_code=204)


@router.post("/{job_id}/retry", status_code=202, response_model=JobAccepted)
async def retry_job(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
    runtime: JobRuntime = Depends(get_runtime),
) -> JobAccepted:
    record = _load_owned(runtime, job_id, user)
    state = enum_value(record.state)
    if state not in RETRYABLE_STATES:
        raise unprocessable("Só é possível retentar jobs em erro ou cancelados.", "NOT_RETRYABLE")
    retried = runtime.supervisor.retry(job_id)
    return JobAccepted(job_id=str(retried.job_id), state=enum_value(retried.state))


@router.get("/{job_id}/artifacts/{kind}")
def download_artifact(
    job_id: str,
    kind: ArtifactKind,
    user: CurrentUser = Depends(get_current_user),
    runtime: JobRuntime = Depends(get_runtime),
) -> FileResponse:
    record = _load_owned(runtime, job_id, user)
    work_dir = record.work_path if hasattr(record, "work_path") else Path(str(record.work_dir))
    path = resolve_artifact(
        work_dir=work_dir,
        kind=kind,
        settings=runtime.settings,
        user_id=user.user_id,
    )
    return FileResponse(path, media_type=media_type_for(kind), filename=path.name)


@router.websocket("/{job_id}/events")
async def job_events(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    try:
        user = await authenticate_websocket(websocket)
    except HTTPException as exc:
        code = 4403 if exc.status_code == 403 else 4401
        await websocket.close(code=code)
        return

    runtime: JobRuntime | None = getattr(websocket.app.state, "runtime", None)
    if runtime is None or not runtime.available:
        await websocket.close(code=1013)
        return

    try:
        record = runtime.machine.get(job_id)
    except JobLookupError:
        await websocket.close(code=4404)
        return
    if str(record.user_id) != user.user_id:
        await websocket.close(code=4403)
        return

    try:
        async for payload in _iter_progress(runtime, job_id, record):
            await websocket.send_json(payload.model_dump())
    except WebSocketDisconnect:
        return
    await websocket.close(code=1000)


@router.get("/{job_id}/events")
async def job_events_sse(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
    runtime: JobRuntime = Depends(get_runtime),
) -> StreamingResponse:
    record = _load_owned(runtime, job_id, user)

    async def generate() -> AsyncIterator[str]:
        async for payload in _iter_progress(runtime, job_id, record):
            yield _sse_frame(payload)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
