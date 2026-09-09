"""Resolve toolchain paths without installing or compiling anything.

COLMAP: never build, never ``apt-get install colmap``. Prefer PATH, then the
user's local CUDA build (``~/colmap/build/...``), then other known prefixes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

COLMAP_CANDIDATES: tuple[Path, ...] = (
    Path.home() / "colmap" / "build" / "src" / "colmap" / "exe" / "colmap",
    Path.home() / "colmap" / "build" / "src" / "exe" / "colmap",
    Path.home() / "colmap" / "install" / "bin" / "colmap",
    Path("/usr/local/bin/colmap"),
    Path("/usr/bin/colmap"),
)

_BUILD_MARKERS = ("cmake", "ninja", "ninja-build", "make")


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def resolve_ffmpeg_bin(configured: str = "ffmpeg") -> str:
    if configured and configured not in {"ffmpeg"} and Path(configured).is_file():
        return str(Path(configured))
    found = shutil.which(configured or "ffmpeg")
    return found or (configured or "ffmpeg")


def resolve_ffprobe_bin(configured: str = "ffprobe") -> str:
    if configured and configured not in {"ffprobe"} and Path(configured).is_file():
        return str(Path(configured))
    found = shutil.which(configured or "ffprobe")
    return found or (configured or "ffprobe")


def _venv_python_exe(venv_root: Path) -> Path:
    if os.name == "nt":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def _is_venv_python(path: Path) -> bool:
    """True when *path* is the venv interpreter (do not follow the symlink).

    ``.venv/bin/python`` is often a symlink to ``/usr/bin/python3``. Invoking
    the system path skips ``site-packages`` (no tyro/gsplat); invoking the
    venv path loads ``pyvenv.cfg`` and the project environment.
    """
    if not path.is_file():
        return False
    return (path.parent.parent / "pyvenv.cfg").is_file()


def _is_generic_python_name(name: str) -> bool:
    if "/" in name or "\\" in name:
        return False
    return name == "python" or name.startswith("python3")


def _is_system_python_path(path: Path) -> bool:
    if _is_venv_python(path):
        return False
    texts = [str(path)]
    try:
        texts.append(str(path.resolve()))
    except OSError:
        pass
    for text in texts:
        parent = str(Path(text).parent)
        base = Path(text).name
        if parent in {"/usr/bin", "/bin", "/usr/local/bin"} and (
            base == "python" or base.startswith("python3")
        ):
            return True
    return False


def _discover_venv_python() -> str | None:
    """Locate the project/runtime venv that has torch/gsplat/tyro."""
    candidates: list[Path] = []
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        candidates.append(_venv_python_exe(Path(virtual_env)))
    here = Path(__file__).resolve()
    if len(here.parents) >= 2:
        candidates.append(_venv_python_exe(here.parents[2] / ".venv"))
    candidates.append(_venv_python_exe(Path.cwd() / ".venv"))
    candidates.append(_venv_python_exe(Path.home() / "gaussian-splating" / ".venv"))
    candidates.append(Path(sys.executable))
    seen: set[str] = set()
    for cand in candidates:
        key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        if _is_venv_python(cand) and _is_executable(cand):
            return str(cand)
        alt = cand.with_name("python3") if cand.name == "python" else None
        if alt is not None and _is_venv_python(alt) and _is_executable(alt):
            return str(alt)
    return None


def resolve_python_bin(configured: str = "python") -> str:
    """Resolve the gsplat trainer interpreter.

    Prefer a project ``.venv`` (torch/gsplat/tyro). Never persist a bare
    system ``/usr/bin/python3`` when a venv exists — that path is not the
    venv even when ``.venv/bin/python`` is a symlink to it.
    """
    configured = (configured or "python").strip() or "python"
    env_tool = (os.environ.get("TOOL_PYTHON") or "").strip()
    discovered = _discover_venv_python()

    for raw in (configured, env_tool):
        if not raw:
            continue
        path = Path(raw)
        if _is_venv_python(path) and _is_executable(path):
            return str(path)
        if path.is_file() and _is_executable(path) and not _is_system_python_path(path):
            return str(path)

    if discovered:
        return discovered

    for raw in (configured, env_tool, "python3", "python"):
        if not raw or _is_generic_python_name(raw):
            which = shutil.which(raw) if raw else None
            if which:
                return which
            continue
        path = Path(raw)
        if path.is_file() and _is_executable(path):
            return str(path)
        which = shutil.which(raw)
        if which:
            return which

    return sys.executable


def resolve_colmap_bin(configured: str = "colmap") -> str | None:
    """Return an existing COLMAP executable, or ``None`` if still missing."""
    env = os.environ.get("COLMAP_BIN") or os.environ.get("TOOL_COLMAP")
    for raw in (configured, env):
        if not raw:
            continue
        path = Path(raw)
        if _is_executable(path):
            return str(path.resolve())
        which = shutil.which(raw)
        if which:
            return which
    for candidate in COLMAP_CANDIDATES:
        if _is_executable(candidate):
            return str(candidate.resolve())
    return None


def resolve_splat_transform(configured: str = "splat-transform") -> str:
    """Localiza o conversor `.ksplat` do usuário; nunca cai para `npx`.

    O fallback para `npx` foi removido: com o binário em ``argv[0]`` o npx
    tentava executar o `.ply` como pacote, e o `@playcanvas/splat-transform`
    do npm não emite `.ksplat` (formato do mkkellogg). Ausência do binário
    vira skip gracioso no export (`.ply` mestre é preservado).
    """
    if configured and Path(configured).is_file():
        return str(Path(configured))
    found = shutil.which(configured or "splat-transform")
    if found:
        return found
    return configured or "splat-transform"


def resolve_simple_trainer(configured: str = "simple_trainer.py") -> str:
    if configured and Path(configured).is_file():
        return str(Path(configured).resolve())
    env = os.environ.get("TOOL_SIMPLE_TRAINER")
    if env and Path(env).is_file():
        return str(Path(env).resolve())
    here = Path(__file__).resolve().parents[1]
    vendor = here / "vendor" / "gsplat-examples" / "examples" / "simple_trainer.py"
    if vendor.is_file():
        return str(vendor)
    home_vendor = Path.home() / "gaussian-splating" / "vendor" / "gsplat-examples" / "examples" / "simple_trainer.py"
    if home_vendor.is_file():
        return str(home_vendor)
    return configured or "simple_trainer.py"


def colmap_build_in_progress() -> bool:
    """True when the user's cmake/ninja/make COLMAP compile is still running."""
    if os.name == "nt":
        return False
    try:
        proc = shutil.which("ps")
        if proc is None:
            return False
        listed = subprocess.run(
            ["ps", "-u", str(os.environ.get("USER") or Path.home().name), "-o", "args="],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        return False
    for line in listed.stdout.splitlines():
        lower = line.lower()
        if "colmap" not in lower:
            continue
        if any(marker in lower for marker in _BUILD_MARKERS):
            if "colmap -h" in lower or "colmap --help" in lower:
                continue
            return True
    return False
