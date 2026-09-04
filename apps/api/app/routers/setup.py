"""Endpoints do Provisioner — pré-checagens, disparo de instalação e progresso."""

from fastapi import APIRouter, HTTPException

from app.schemas.setup import HealthReportSchema, InstallAcceptedSchema, SetupProgressSchema
from app.services import provisioner_service
from app.services.provisioner_service import SetupAlreadyRunningError

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", response_model=HealthReportSchema)
def setup_status() -> HealthReportSchema:
    """Pré-checagens do ambiente: GPU NVIDIA/driver/CUDA, WSL2, disco, RAM, ffmpeg, COLMAP e Python."""
    return HealthReportSchema.model_validate(provisioner_service.get_health())


@router.post("/install", status_code=202, response_model=InstallAcceptedSchema)
def setup_install() -> InstallAcceptedSchema:
    """Dispara o provisionamento assíncrono (Fase 0: instalações são stubs documentados)."""
    try:
        provisioner_service.start_install()
    except SetupAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return InstallAcceptedSchema(
        state="running",
        message="Provisionamento iniciado. Acompanhe o progresso em GET /setup/progress.",
    )


@router.get("/progress", response_model=SetupProgressSchema)
def setup_progress() -> SetupProgressSchema:
    """Fotografia do progresso do provisionamento (a UI faz polling a cada ~1,5 s)."""
    return SetupProgressSchema.model_validate(provisioner_service.get_progress())
