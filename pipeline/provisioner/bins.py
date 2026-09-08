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


def resolve_python_bin(configured: str = "python") -> str:
    if configured and Path(configured).is_file():
        return str(Path(configured))
    found = shutil.which(configured) or shutil.which("python3")
    return found or sys.executable


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
    if configured and Path(configured).is_file():
        return str(Path(configured))
    found = shutil.which(configured or "splat-transform")
    if found:
        return found
    npx = shutil.which("npx")
    if npx:
        return npx
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
