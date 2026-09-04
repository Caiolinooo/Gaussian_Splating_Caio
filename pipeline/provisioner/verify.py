"""Verificações pós-instalação (smoke tests).

Fase 0: apenas as verificações **leves** executam de verdade (ffmpeg, COLMAP e
Python — as mesmas sondas da detecção, reutilizadas como smoke tests). As
verificações **pesadas** (import do gsplat, CUDA do PyTorch, render smoke test)
ficam como stubs documentados até que as instalações reais existam.
"""

from __future__ import annotations

from provisioner.detect import ComponentCheck, Status, detect_colmap, detect_ffmpeg, detect_python
from provisioner.plan import LogFn, StepResult, StepStatus


def verify_ffmpeg() -> ComponentCheck:
    """Smoke test leve: ``ffmpeg -version``."""
    return detect_ffmpeg()


def verify_colmap() -> ComponentCheck:
    """Smoke test leve: ``colmap -h``."""
    return detect_colmap()


def verify_python() -> ComponentCheck:
    """Smoke test leve: versão do interpretador em execução."""
    return detect_python()


def run_verifications(log: LogFn) -> StepResult:
    """Roda as verificações leves e registra as pesadas como planejadas."""
    log("Executando verificações pós-instalação (leves)…")
    failures = 0
    for verify in (verify_ffmpeg, verify_colmap, verify_python):
        check = verify()
        log(f"[{check.status.value}] {check.name}: {check.message}")
        if check.status is Status.ERROR:
            failures += 1

    log("STUB: import test do gsplat e checagem de CUDA do PyTorch — planejados para a instalação real.")
    log("STUB: render smoke test (rasterização mínima de splats) — planejado para a instalação real.")

    if failures:
        return StepResult("verify", StepStatus.ERROR, "Falhas nas verificações pós-instalação.")
    return StepResult(
        "verify",
        StepStatus.DONE,
        "Verificações leves concluídas; testes pesados (gsplat/CUDA/render) planejados.",
    )
