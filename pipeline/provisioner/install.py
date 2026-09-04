"""Plano de provisionamento e rotinas de instalação.

⚠️  FASE 0 — STUBS DOCUMENTADOS: as rotinas de instalação **não** baixam nem
instalam nada ainda. Elas registram no log exatamente o que será feito e
retornam ``StepStatus.SKIPPED``. As URLs oficiais planejadas estão consolidadas
nas constantes abaixo (fonte de verdade para a implementação real).

Plano real (próximas fases):
1. ``ffmpeg``      — baixar build essentials (gyan.dev), extrair e registrar no PATH.
2. ``colmap``      — baixar release Windows com CUDA (github.com/colmap/colmap).
3. ``python-env``  — garantir WSL2 + Ubuntu, criar venv e instalar PyTorch com
                     CUDA via índice oficial de wheels.
4. ``gsplat``      — instalar wheel pré-compilada (decisão 2026-09-04), sem
                     compilação local de extensões CUDA.
"""

from __future__ import annotations

from provisioner.health import run_all_checks
from provisioner.plan import (
    PROVISIONING_PLAN,
    InstallStep,
    LogFn,
    StepEventFn,
    StepResult,
    StepStatus,
)
from provisioner.verify import run_verifications

__all__ = [
    "PROVISIONING_PLAN",
    "InstallStep",
    "StepResult",
    "StepStatus",
    "install_colmap",
    "install_ffmpeg",
    "install_gsplat",
    "run_provisioning",
    "setup_python_env",
]

# ─── URLs oficiais planejadas (usar na implementação real) ───────────────────
FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
COLMAP_RELEASES_URL = "https://github.com/colmap/colmap/releases"  # build Windows com CUDA
WSL_INSTALL_GUIDE_URL = "https://learn.microsoft.com/pt-br/windows/wsl/install"
PYTORCH_WHEELS_INDEX_URL = "https://download.pytorch.org/whl/cu126"  # CUDA 12.6
GSPLAT_PRECOMPILED_WHEELS_URL = "https://docs.gsplat.studio/whl/pt26/cu126"  # wheel pré-compilada

_STUB_MESSAGE = "Instalação automatizada planejada para a próxima fase (stub da Fase 0)."


def install_ffmpeg(log: LogFn) -> StepResult:
    """STUB: instalaria o FFmpeg a partir da build oficial para Windows."""
    log(f"STUB: baixaria o FFmpeg de {FFMPEG_DOWNLOAD_URL}")
    log("STUB: extrairia o arquivo, registraria o diretório no PATH e validaria com 'ffmpeg -version'.")
    return StepResult("ffmpeg", StepStatus.SKIPPED, _STUB_MESSAGE)


def install_colmap(log: LogFn) -> StepResult:
    """STUB: instalaria o COLMAP (release Windows com CUDA)."""
    log(f"STUB: baixaria o COLMAP (build CUDA) de {COLMAP_RELEASES_URL}")
    log("STUB: extrairia os binários, registraria no PATH e validaria com 'colmap -h'.")
    return StepResult("colmap", StepStatus.SKIPPED, _STUB_MESSAGE)


def setup_python_env(log: LogFn) -> StepResult:
    """STUB: prepararia o ambiente Python dentro do WSL2 com PyTorch + CUDA."""
    log(f"STUB: garantiria WSL2 + Ubuntu (guia: {WSL_INSTALL_GUIDE_URL})")
    log(f"STUB: criaria a venv do pipeline e instalaria PyTorch via {PYTORCH_WHEELS_INDEX_URL}")
    return StepResult("python-env", StepStatus.SKIPPED, _STUB_MESSAGE)


def install_gsplat(log: LogFn) -> StepResult:
    """STUB: instalaria o gsplat via wheel pré-compilada (sem build CUDA local)."""
    log(f"STUB: instalaria o gsplat da wheel pré-compilada em {GSPLAT_PRECOMPILED_WHEELS_URL}")
    log("STUB: validaria com um import test ('import gsplat') dentro do WSL2.")
    return StepResult("gsplat", StepStatus.SKIPPED, _STUB_MESSAGE)


def run_provisioning(log: LogFn, on_step: StepEventFn | None = None) -> list[StepResult]:
    """Executa o plano de provisionamento na ordem, emitindo logs em pt-BR.

    ``on_step`` (opcional) recebe eventos de início/fim de cada etapa para a UI
    acompanhar o progresso em tempo real. Na Fase 0 apenas as etapas de
    detecção e verificação executam de verdade; as demais retornam ``SKIPPED``
    com o plano registrado no log.
    """

    def emit(key: str, status: StepStatus, message: str | None = None) -> None:
        if on_step is not None:
            on_step(key, status, message)

    results: list[StepResult] = []

    emit("detect", StepStatus.RUNNING)
    log("Iniciando a detecção do ambiente…")
    report = run_all_checks()
    for check in report.checks:
        log(f"[{check.status.value}] {check.name}: {check.message}")
    log(f"Detecção concluída — estado geral: {report.overall.value}.")
    detect_result = StepResult("detect", StepStatus.DONE, "Detecção do ambiente concluída.")
    results.append(detect_result)
    emit("detect", detect_result.status, detect_result.message)

    routines = (
        ("ffmpeg", install_ffmpeg),
        ("colmap", install_colmap),
        ("python-env", setup_python_env),
        ("gsplat", install_gsplat),
    )
    for key, routine in routines:
        emit(key, StepStatus.RUNNING)
        result = routine(log)
        results.append(result)
        emit(key, result.status, result.message)

    emit("verify", StepStatus.RUNNING)
    verify_result = run_verifications(log)
    results.append(verify_result)
    emit("verify", verify_result.status, verify_result.message)

    log("Provisionamento da Fase 0 concluído (instalações reais permanecem como stubs).")
    return results
