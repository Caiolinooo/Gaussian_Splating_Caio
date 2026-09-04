"""Relatório de saúde do ambiente — agrega todas as detecções do Provisioner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from provisioner.detect import (
    ComponentCheck,
    Status,
    detect_colmap,
    detect_disk,
    detect_ffmpeg,
    detect_gpu,
    detect_memory,
    detect_python,
    detect_wsl,
)

#: Checagens executadas, na ordem exibida pela UI de Setup.
CHECKERS: Final = (
    detect_gpu,
    detect_wsl,
    detect_disk,
    detect_memory,
    detect_ffmpeg,
    detect_colmap,
    detect_python,
)

#: Componentes sem os quais nem o provisionamento automático deve começar.
CRITICAL_KEYS: Final = frozenset({"gpu", "wsl2", "disk", "memory"})


@dataclass
class HealthReport:
    """Fotografia do ambiente consumida pela API (``GET /setup/status``)."""

    checks: list[ComponentCheck]
    overall: Status
    ready: bool
    generated_at: str


def run_all_checks() -> HealthReport:
    """Executa todas as detecções e consolida o estado geral do ambiente.

    - ``ready``: True apenas quando nenhum componente crítico falhou e nada está
      ausente/com erro (avisos não bloqueiam).
    - ``overall``: pior estado agregado (error > missing > warning > unknown > ok),
      com componentes críticos elevando ``missing`` a ``error`` no consolidado.
    """
    checks = [checker() for checker in CHECKERS]

    critical_failed = any(
        check.key in CRITICAL_KEYS and check.status in (Status.ERROR, Status.MISSING) for check in checks
    )
    any_error = any(check.status is Status.ERROR for check in checks)
    any_missing = any(check.status is Status.MISSING for check in checks)
    any_warning = any(check.status is Status.WARNING for check in checks)

    if critical_failed or any_error:
        overall = Status.ERROR
    elif any_missing:
        overall = Status.WARNING  # ausências de ffmpeg/COLMAP são justamente o que o instalador resolve
    elif any_warning:
        overall = Status.WARNING
    else:
        overall = Status.OK

    ready = not critical_failed and not any_error and not any_missing
    return HealthReport(
        checks=checks,
        overall=overall,
        ready=ready,
        generated_at=datetime.now(UTC).isoformat(),
    )
