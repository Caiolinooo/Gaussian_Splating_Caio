"""Liveness da API."""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Confirma que a API local está de pé (usado pelo app desktop e pela UI)."""
    return HealthResponse(status="ok", service=settings.app_name, version=settings.version)
