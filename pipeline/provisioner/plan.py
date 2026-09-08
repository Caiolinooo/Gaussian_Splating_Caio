"""Tipos e plano do provisionamento — sem dependências internas.

Separado de ``install``/``verify`` para evitar import circular entre eles
(ambos consomem estes tipos; ``install`` orquestra ``verify``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

LogFn = Callable[[str], None]

#: Evento de mudança de estado de etapa: (key, status, mensagem opcional).
StepEventFn = Callable[[str, "StepStatus", "str | None"], None]


class StepStatus(StrEnum):
    """Estado de uma etapa do provisionamento."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(frozen=True)
class InstallStep:
    """Etapa do plano, na ordem exibida/executada."""

    key: str
    title: str  # pt-BR, exibido na UI de Setup


@dataclass
class StepResult:
    """Resultado da execução de uma etapa."""

    key: str
    status: StepStatus
    message: str
    log: list[str] = field(default_factory=list)


#: Plano ordenado consumido pela API (``POST /setup/install``).
PROVISIONING_PLAN: list[InstallStep] = [
    InstallStep("detect", "Detectar componentes do ambiente"),
    InstallStep("ffmpeg", "Instalar FFmpeg"),
    InstallStep("colmap", "Localizar COLMAP (compilação do usuário)"),
    InstallStep("python-env", "Preparar ambiente Python (PyTorch + CUDA)"),
    InstallStep("gsplat", "Instalar gsplat (wheel pré-compilada)"),
    InstallStep("verify", "Verificar saúde pós-instalação"),
]
