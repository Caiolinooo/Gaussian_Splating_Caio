"""Rotinas de instalação reais (Linux/GPU) — COLMAP nunca é compilado daqui.

ffmpeg / PyTorch / gsplat: instala se ausente e o ambiente permitir.
COLMAP: só localiza o binário do usuário (PATH ou ~/colmap/build). Nunca
``apt-get install colmap``, nunca cmake/ninja/make.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys

from provisioner.bins import (
    colmap_build_in_progress,
    resolve_colmap_bin,
    resolve_ffmpeg_bin,
)
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

try:
    from train.locate import ensure_simple_trainer
except ImportError:
    ensure_simple_trainer = None

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

FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
COLMAP_RELEASES_URL = "https://github.com/colmap/colmap/releases"
WSL_INSTALL_GUIDE_URL = "https://learn.microsoft.com/pt-br/windows/wsl/install"
PYTORCH_WHEELS_INDEX_URL = "https://download.pytorch.org/whl/cu128"
GSPLAT_PRECOMPILED_WHEELS_URL = "https://docs.gsplat.studio/whl"

PIP_TIMEOUT_S = 1800
APT_TIMEOUT_S = 600


def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _gpu_linux() -> bool:
    return platform.system() == "Linux" and shutil.which("nvidia-smi") is not None


def _torch_ready(log: LogFn) -> bool:
    probe = _run(
        [sys.executable, "-c", "import torch; print(int(torch.cuda.is_available()))"],
        timeout=30,
    )
    if probe.returncode == 0 and probe.stdout.strip().startswith("1"):
        log(f"PyTorch+CUDA já disponível em {sys.executable}.")
        return True
    return False


def _gsplat_ready(log: LogFn) -> bool:
    probe = _run([sys.executable, "-c", "import gsplat; print('ok')"], timeout=30)
    if probe.returncode == 0:
        log(f"gsplat já importável em {sys.executable}.")
        return True
    return False


def install_ffmpeg(log: LogFn) -> StepResult:
    found = resolve_ffmpeg_bin("ffmpeg")
    if shutil.which(found) or (found != "ffmpeg" and os.path.isfile(found)):
        log(f"FFmpeg já disponível: {found}")
        return StepResult("ffmpeg", StepStatus.DONE, f"FFmpeg já instalado ({found}).")

    if platform.system() == "Linux" and shutil.which("sudo"):
        log("Instalando FFmpeg via apt (sem tocar no COLMAP)…")
        try:
            result = _run(
                ["sudo", "-n", "apt-get", "install", "-y", "ffmpeg"],
                timeout=APT_TIMEOUT_S,
            )
        except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError) as exc:
            log(f"apt ffmpeg falhou: {exc}")
            return StepResult("ffmpeg", StepStatus.SKIPPED, "Não foi possível instalar o FFmpeg automaticamente.")
        if result.returncode == 0 and shutil.which("ffmpeg"):
            path = shutil.which("ffmpeg") or "ffmpeg"
            log(f"FFmpeg instalado: {path}")
            return StepResult("ffmpeg", StepStatus.DONE, f"FFmpeg instalado ({path}).")
        log((result.stderr or result.stdout or "apt ffmpeg falhou").strip()[:400])

    log(f"FFmpeg ausente. Build Windows documentada: {FFMPEG_DOWNLOAD_URL}")
    return StepResult("ffmpeg", StepStatus.SKIPPED, "FFmpeg não encontrado e instalação automática indisponível.")


def install_colmap(log: LogFn) -> StepResult:
    """Nunca compila nem instala COLMAP — só usa o binário do usuário."""
    found = resolve_colmap_bin("colmap")
    if found:
        log(f"COLMAP do usuário localizado: {found}")
        return StepResult("colmap", StepStatus.DONE, f"COLMAP localizado ({found}).")

    if colmap_build_in_progress():
        log("Compilação local do COLMAP em andamento — não interrompida, não instalo via apt.")
        return StepResult(
            "colmap",
            StepStatus.SKIPPED,
            "Aguardando a compilação local do COLMAP terminar.",
        )

    log("COLMAP ausente. Não vou compilá-lo nem instalá-lo via gerenciador de pacotes.")
    log(f"Quando a build acabar, o binário esperado é ~/colmap/build/src/colmap/exe/colmap ({COLMAP_RELEASES_URL}).")
    return StepResult(
        "colmap",
        StepStatus.SKIPPED,
        "COLMAP ainda não está no PATH; o app usará a compilação local quando existir.",
    )


def setup_python_env(log: LogFn) -> StepResult:
    if _torch_ready(log):
        return StepResult("python-env", StepStatus.DONE, "PyTorch+CUDA já prontos.")

    if not _gpu_linux():
        log("PyTorch+CUDA só instala automaticamente em Linux com nvidia-smi.")
        log(f"Índice planejado: {PYTORCH_WHEELS_INDEX_URL}")
        if platform.system() == "Windows":
            log(f"No Windows o alvo continua WSL2 ({WSL_INSTALL_GUIDE_URL}).")
        return StepResult(
            "python-env",
            StepStatus.SKIPPED,
            "Sem GPU Linux neste processo — PyTorch+CUDA não instalado.",
        )

    log(f"Instalando PyTorch CUDA via {PYTORCH_WHEELS_INDEX_URL} (L4 / driver CUDA 13.x)…")
    try:
        result = _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "torch",
                "torchvision",
                "--index-url",
                PYTORCH_WHEELS_INDEX_URL,
            ],
            timeout=PIP_TIMEOUT_S,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError) as exc:
        log(f"pip torch falhou: {exc}")
        return StepResult("python-env", StepStatus.ERROR, "Falha ao instalar PyTorch.")
    if result.returncode != 0:
        log((result.stderr or result.stdout or "pip torch falhou").strip()[:600])
        return StepResult("python-env", StepStatus.ERROR, "pip do PyTorch retornou erro.")
    if _torch_ready(log):
        return StepResult("python-env", StepStatus.DONE, "PyTorch+CUDA instalados.")
    log("PyTorch instalado, mas CUDA não ficou disponível.")
    return StepResult("python-env", StepStatus.ERROR, "PyTorch sem CUDA após a instalação.")


def install_gsplat(log: LogFn) -> StepResult:
    if _gsplat_ready(log):
        return StepResult("gsplat", StepStatus.DONE, "gsplat já instalado.")

    if not _gpu_linux():
        log(f"Wheel pré-compilada documentada: {GSPLAT_PRECOMPILED_WHEELS_URL}")
        return StepResult("gsplat", StepStatus.SKIPPED, "gsplat só instala automaticamente em Linux com GPU.")

    log("Instalando gsplat + dependências leves do trainer…")
    try:
        result = _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "gsplat",
                "ninja",
                "tyro",
                "tqdm",
                "pillow",
                "imageio",
                "tensorboard",
                "jaxtyping",
                "rich",
            ],
            timeout=PIP_TIMEOUT_S,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError) as exc:
        log(f"pip gsplat falhou: {exc}")
        return StepResult("gsplat", StepStatus.ERROR, "Falha ao instalar gsplat.")
    if result.returncode != 0:
        log((result.stderr or result.stdout or "pip gsplat falhou").strip()[:600])
        return StepResult("gsplat", StepStatus.ERROR, "pip do gsplat retornou erro.")
    if _gsplat_ready(log):
        if ensure_simple_trainer is not None:
            ensure_simple_trainer(log)
        return StepResult("gsplat", StepStatus.DONE, "gsplat instalado.")
    return StepResult("gsplat", StepStatus.ERROR, "gsplat não importou após o pip.")


def run_provisioning(log: LogFn, on_step: StepEventFn | None = None) -> list[StepResult]:
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

    log("Provisionamento concluído (COLMAP só é localizado, nunca compilado daqui).")
    return results
