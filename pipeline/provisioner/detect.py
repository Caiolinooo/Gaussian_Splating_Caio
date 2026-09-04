"""Detecções reais de ambiente (Windows 11 / WSL2) para o Provisioner.

Todas as rotinas são **somente-leitura**: nada aqui instala ou modifica o
sistema. O alvo principal é Windows 11 (host do app Tauri); em Linux/macOS as
checagens específicas de Windows respondem ``Status.UNKNOWN`` com mensagem
clara, e as demais funcionam normalmente.
"""

from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

COMMAND_TIMEOUT_S = 15
MIN_DISK_FREE_GB = 60.0
WARN_DISK_FREE_GB = 25.0
MIN_RAM_GB = 7.5
# 15.5 GiB ≈ limiar real de uma máquina "16 GB" (que reporta ~15,9 GiB).
RECOMMENDED_RAM_GB = 15.5
MIN_PYTHON_VERSION = (3, 10)


class Status(StrEnum):
    """Estado de uma checagem de componente."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass
class ComponentCheck:
    """Resultado da checagem de um componente do ambiente.

    ``message`` e ``fix_hint`` são escritos em pt-BR, prontos para a UI de Setup.
    """

    key: str
    name: str
    status: Status
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    fix_hint: str | None = None


def _run(command: list[str], timeout: int = COMMAND_TIMEOUT_S) -> subprocess.CompletedProcess[str] | None:
    """Executa um comando externo de forma defensiva.

    Retorna ``None`` quando o executável não existe, estoura o timeout ou o SO
    recusa a execução — nunca propaga exceção para o chamador.
    """
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        return None


def _run_wsl(args: list[str], timeout: int = COMMAND_TIMEOUT_S) -> tuple[int, str] | None:
    """Executa ``wsl.exe`` tratando a saída UTF-16 que algumas builds emitem.

    Retorna ``(returncode, stdout_limpo)`` ou ``None`` se indisponível.
    """
    try:
        proc = subprocess.run(["wsl", *args], capture_output=True, timeout=timeout, check=False)
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        return None
    raw = proc.stdout
    if b"\x00" in raw[:16]:
        text = raw.decode("utf-16-le", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")
    return proc.returncode, text.replace("\x00", "").strip()


def detect_gpu() -> ComponentCheck:
    """GPU NVIDIA + driver + versão CUDA do driver, via ``nvidia-smi``."""
    key, name = "gpu", "GPU NVIDIA"
    fix = (
        "Instale ou atualize o driver NVIDIA (https://www.nvidia.com.br/Download/index.aspx?lang=br) "
        "e reinicie o computador. O treino de Gaussian Splatting exige GPU NVIDIA com CUDA."
    )
    if shutil.which("nvidia-smi") is None:
        return ComponentCheck(
            key, name, Status.MISSING, "Nenhuma GPU NVIDIA detectada (nvidia-smi ausente).", fix_hint=fix
        )

    listed = _run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]
    )
    if listed is None or listed.returncode != 0 or not listed.stdout.strip():
        return ComponentCheck(
            key,
            name,
            Status.MISSING,
            "nvidia-smi não respondeu — GPU/driver NVIDIA não detectados.",
            fix_hint=fix,
        )

    gpus: list[dict[str, str]] = []
    for line in listed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 3:
            gpus.append({"name": parts[0], "driver": parts[1], "memory": parts[2]})

    cuda_version: str | None = None
    full = _run(["nvidia-smi"])
    if full is not None and full.returncode == 0:
        match = re.search(r"CUDA Version:\s*([\d.]+)", full.stdout)
        if match:
            cuda_version = match.group(1)

    names = ", ".join(gpu["name"] for gpu in gpus)
    details: dict[str, Any] = {"gpus": gpus, "cuda_driver_version": cuda_version}
    return ComponentCheck(
        key,
        name,
        Status.OK,
        f"{len(gpus)} GPU(s) detectada(s): {names} (driver {gpus[0]['driver']}, CUDA {cuda_version or 'n/d'}).",
        details=details,
    )


def detect_wsl() -> ComponentCheck:
    """WSL2 habilitado e com pelo menos uma distribuição instalada."""
    key, name = "wsl2", "WSL2"
    fix = (
        "Habilite o WSL2 (o instalador automatizará esta etapa; referência: "
        "https://learn.microsoft.com/pt-br/windows/wsl/install) e reinicie o computador."
    )
    if platform.system() != "Windows":
        return ComponentCheck(key, name, Status.UNKNOWN, "A checagem de WSL2 só se aplica ao Windows.")
    if shutil.which("wsl") is None and not os.path.exists(r"C:\Windows\System32\wsl.exe"):
        return ComponentCheck(key, name, Status.MISSING, "WSL não está instalado neste Windows.", fix_hint=fix)

    status = _run_wsl(["--status"])
    if status is None:
        return ComponentCheck(
            key, name, Status.MISSING, "WSL não respondeu — provavelmente não está habilitado.", fix_hint=fix
        )

    returncode, output = status
    if returncode != 0:
        return ComponentCheck(
            key, name, Status.MISSING, "WSL presente, mas não está habilitado/configurado.", fix_hint=fix
        )

    distros = _run_wsl(["--list", "--quiet"])
    distro_names = [line.strip() for line in (distros[1].splitlines() if distros else []) if line.strip()]
    details: dict[str, Any] = {"distros": distro_names, "status_output": output}
    if not distro_names:
        return ComponentCheck(
            key,
            name,
            Status.WARNING,
            "WSL2 habilitado, mas nenhuma distribuição Linux instalada (ex.: Ubuntu).",
            details=details,
            fix_hint="Instale uma distribuição (ex.: Ubuntu) — o instalador cuidará disso automaticamente.",
        )
    return ComponentCheck(
        key,
        name,
        Status.OK,
        f"WSL2 habilitado com {len(distro_names)} distribuição(ões): {', '.join(distro_names)}.",
        details=details,
    )


def detect_disk() -> ComponentCheck:
    """Espaço livre no volume de trabalho (pipeline precisa de folga para datasets e builds)."""
    key, name = "disk", "Espaço em disco"
    usage = shutil.disk_usage(os.path.abspath(os.sep))
    free_gb = usage.free / (1024**3)
    total_gb = usage.total / (1024**3)
    details = {"free_gb": round(free_gb, 1), "total_gb": round(total_gb, 1), "path": os.path.abspath(os.sep)}
    if free_gb >= MIN_DISK_FREE_GB:
        status, message = Status.OK, f"{free_gb:.0f} GB livres de {total_gb:.0f} GB."
    elif free_gb >= WARN_DISK_FREE_GB:
        status = Status.WARNING
        message = f"Apenas {free_gb:.0f} GB livres — o recomendado é ≥ {MIN_DISK_FREE_GB:.0f} GB."
    else:
        status = Status.ERROR
        message = f"Somente {free_gb:.0f} GB livres — insuficiente para o pipeline."
    return ComponentCheck(
        key,
        name,
        status,
        message,
        details=details,
        fix_hint=(
            None
            if status is Status.OK
            else "Libere espaço em disco: COLMAP, PyTorch/CUDA, gsplat e datasets ocupam dezenas de GB."
        ),
    )


def _total_memory_bytes() -> int | None:
    """Memória física total em bytes (Windows via Win32; Linux via /proc/meminfo)."""
    system = platform.system()
    if system == "Windows":

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
            return int(stat.ullTotalPhys)
        return None
    if system == "Linux":
        try:
            with open("/proc/meminfo", encoding="utf-8") as meminfo:
                for line in meminfo:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) * 1024
        except OSError:
            return None
    return None


def detect_memory() -> ComponentCheck:
    """Memória RAM total (recomendado ≥ 16 GB para treino 3DGS)."""
    key, name = "memory", "Memória RAM"
    total = _total_memory_bytes()
    if total is None:
        return ComponentCheck(key, name, Status.UNKNOWN, "Não foi possível determinar a memória RAM total.")
    total_gb = total / (1024**3)
    details = {"total_gb": round(total_gb, 1)}
    recommended_label = "16 GB"
    if total_gb >= RECOMMENDED_RAM_GB:
        return ComponentCheck(
            key,
            name,
            Status.OK,
            f"{total_gb:.0f} GB de RAM (recomendado ≥ {recommended_label}).",
            details=details,
        )
    if total_gb >= MIN_RAM_GB:
        return ComponentCheck(
            key,
            name,
            Status.WARNING,
            f"{total_gb:.0f} GB de RAM — funciona, mas o recomendado é ≥ {recommended_label}.",
            details=details,
        )
    return ComponentCheck(
        key,
        name,
        Status.ERROR,
        f"Apenas {total_gb:.0f} GB de RAM — insuficiente para o pipeline.",
        details=details,
        fix_hint=(
            f"O pipeline de treino exige ao menos 8 GB de RAM (recomendado {recommended_label})."
        ),
    )


def detect_ffmpeg() -> ComponentCheck:
    """FFmpeg disponível no PATH (extração de frames de vídeo)."""
    key, name = "ffmpeg", "FFmpeg"
    path = shutil.which("ffmpeg")
    if path is None:
        return ComponentCheck(
            key,
            name,
            Status.MISSING,
            "FFmpeg não encontrado no PATH.",
            fix_hint="O Provisioner instalará o FFmpeg automaticamente (builds oficiais: https://www.gyan.dev/ffmpeg/builds/).",
        )
    version: str | None = None
    result = _run(["ffmpeg", "-version"])
    if result is not None and result.returncode == 0:
        match = re.search(r"ffmpeg version\s+(\S+)", result.stdout)
        if match:
            version = match.group(1)
    return ComponentCheck(
        key,
        name,
        Status.OK,
        f"FFmpeg {version or 'detectado'} disponível.",
        details={"path": path, "version": version},
    )


def detect_colmap() -> ComponentCheck:
    """COLMAP disponível no PATH (SfM — structure-from-motion)."""
    key, name = "colmap", "COLMAP"
    path = shutil.which("colmap")
    if path is None:
        return ComponentCheck(
            key,
            name,
            Status.MISSING,
            "COLMAP não encontrado no PATH.",
            fix_hint="O Provisioner instalará o COLMAP automaticamente (releases oficiais com CUDA: https://github.com/colmap/colmap/releases).",
        )
    first_line: str | None = None
    result = _run(["colmap", "-h"])
    if result is not None and result.stdout:
        first_line = result.stdout.splitlines()[0].strip() or None
    return ComponentCheck(
        key,
        name,
        Status.OK,
        f"COLMAP disponível ({first_line or 'versão não identificada'}).",
        details={"path": path, "banner": first_line},
    )


def detect_python() -> ComponentCheck:
    """Versão do interpretador Python que hospeda o Provisioner/API."""
    key, name = "python", "Python"
    version = platform.python_version()
    current = sys.version_info[:2]
    details = {"version": version, "executable": sys.executable}
    if current >= MIN_PYTHON_VERSION:
        return ComponentCheck(key, name, Status.OK, f"Python {version} ({sys.executable}).", details=details)
    required = ".".join(str(part) for part in MIN_PYTHON_VERSION)
    return ComponentCheck(
        key,
        name,
        Status.ERROR,
        f"Python {version} é mais antigo que o mínimo exigido ({required}+).",
        details=details,
        fix_hint=f"Instale o Python {required} ou superior (https://www.python.org/downloads/).",
    )
