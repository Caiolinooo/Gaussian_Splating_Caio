"""Orquestração do Provisioner para a API.

Fase 0: estado em memória, um provisionamento por vez, execução em thread
separada (as detecções chamam subprocessos bloqueantes como ``nvidia-smi`` e
``wsl --status``). Nas próximas fases isto vira um job persistente na fila.
"""

from __future__ import annotations

import threading
import traceback
from collections import deque
from datetime import UTC, datetime
from typing import Any

from provisioner.health import HealthReport, run_all_checks
from provisioner.install import PROVISIONING_PLAN, StepStatus, run_provisioning

MAX_LOG_LINES = 500
_TERMINAL_STEP_STATUSES = {StepStatus.DONE.value, StepStatus.SKIPPED.value, StepStatus.ERROR.value}


class SetupAlreadyRunningError(RuntimeError):
    """Já existe um provisionamento em andamento."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SetupSession:
    """Sessão única de provisionamento, protegida por lock (thread da API × thread do worker)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self.state = "idle"  # idle | running | done | error
        self.steps: list[dict[str, Any]] = [
            {"key": step.key, "title": step.title, "status": StepStatus.PENDING.value, "detail": None}
            for step in PROVISIONING_PLAN
        ]
        self.log: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self.updated_at = _utc_now()

    def start(self) -> None:
        with self._lock:
            if self.state == "running":
                raise SetupAlreadyRunningError(
                    "Já existe um provisionamento em andamento. Aguarde a conclusão ou recarregue o progresso."
                )
            self._reset_locked()
            self.state = "running"
            self._log_locked("Provisionamento iniciado.")
        worker = threading.Thread(target=self._execute, name="provisioner-worker", daemon=True)
        worker.start()

    def _execute(self) -> None:
        try:
            run_provisioning(self._log, self._on_step)
        except Exception:  # noqa: BLE001 — última linha de defesa: reportar à UI, nunca derrubar a API
            with self._lock:
                self.state = "error"
                self._log_locked("Falha inesperada durante o provisionamento:")
                for line in traceback.format_exc().splitlines():
                    self._log_locked(line)
        else:
            with self._lock:
                self.state = "done"
                self._log_locked("Provisionamento finalizado.")
                self.updated_at = _utc_now()

    def _log(self, line: str) -> None:
        with self._lock:
            self._log_locked(line)

    def _log_locked(self, line: str) -> None:
        self.log.append(f"[{_utc_now()}] {line}")
        self.updated_at = _utc_now()

    def _on_step(self, key: str, status: StepStatus, message: str | None) -> None:
        with self._lock:
            for step in self.steps:
                if step["key"] == key:
                    step["status"] = status.value
                    step["detail"] = message
            self.updated_at = _utc_now()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            finished = sum(1 for step in self.steps if step["status"] in _TERMINAL_STEP_STATUSES)
            percent = round(finished / len(self.steps) * 100) if self.steps else 0
            return {
                "state": self.state,
                "percent": percent,
                "steps": [dict(step) for step in self.steps],
                "log": list(self.log),
                "updated_at": self.updated_at,
            }


session = SetupSession()


def get_health() -> HealthReport:
    """Roda as pré-checagens do ambiente (bloqueante — FastAPI executa em threadpool)."""
    return run_all_checks()


def start_install() -> None:
    """Dispara o provisionamento assíncrono (202 na API)."""
    session.start()


def get_progress() -> dict[str, Any]:
    """Fotografia atual do progresso para o polling da UI."""
    return session.snapshot()
