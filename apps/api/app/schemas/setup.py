"""Schemas dos endpoints do Provisioner (UI de Setup)."""

from typing import Any

from provisioner.detect import Status
from pydantic import BaseModel, ConfigDict


class ComponentCheckSchema(BaseModel):
    """Resultado de uma checagem de componente (espelha provisioner.detect.ComponentCheck)."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    name: str
    status: Status
    message: str
    details: dict[str, Any] = {}
    fix_hint: str | None = None


class HealthReportSchema(BaseModel):
    """Relatório de saúde do ambiente (espelha provisioner.health.HealthReport)."""

    model_config = ConfigDict(from_attributes=True)

    checks: list[ComponentCheckSchema]
    overall: Status
    ready: bool
    generated_at: str


class SetupStepSchema(BaseModel):
    """Etapa do provisionamento para a UI de progresso."""

    key: str
    title: str
    status: str
    detail: str | None = None


class SetupProgressSchema(BaseModel):
    """Fotografia do progresso do provisionamento (polling pela UI)."""

    state: str  # idle | running | done | error
    percent: int
    steps: list[SetupStepSchema]
    log: list[str]
    updated_at: str


class InstallAcceptedSchema(BaseModel):
    """Resposta do POST /setup/install (202)."""

    state: str
    message: str
