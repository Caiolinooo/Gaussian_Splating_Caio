"""Verificações pós-instalação (ffmpeg, COLMAP do usuário, Python, torch, gsplat)."""

from __future__ import annotations

from provisioner.detect import (
    ComponentCheck,
    Status,
    detect_colmap,
    detect_ffmpeg,
    detect_gsplat,
    detect_python,
    detect_pytorch,
)
from provisioner.plan import LogFn, StepResult, StepStatus


def verify_ffmpeg() -> ComponentCheck:
    return detect_ffmpeg()


def verify_colmap() -> ComponentCheck:
    return detect_colmap()


def verify_python() -> ComponentCheck:
    return detect_python()


def run_verifications(log: LogFn) -> StepResult:
    log("Executando verificações pós-instalação…")
    failures = 0
    for verify in (verify_ffmpeg, verify_colmap, verify_python, detect_pytorch, detect_gsplat):
        check = verify()
        log(f"[{check.status.value}] {check.name}: {check.message}")
        if check.status is Status.ERROR:
            failures += 1

    if failures:
        return StepResult("verify", StepStatus.ERROR, "Falhas nas verificações pós-instalação.")
    return StepResult("verify", StepStatus.DONE, "Verificações pós-instalação concluídas.")
