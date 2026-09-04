"""PlayCanvas splat-transform and ffmpeg thumbnail command builders."""

from __future__ import annotations

from pathlib import Path

from export.config import ExportConfig


def format_floater_args(config: ExportConfig) -> str:
    """``--filter-floaters [size,op,min]`` value (defaults 0.05,0.1,0.004)."""
    return (
        f"{config.floater_voxel:g},"
        f"{config.floater_opacity:g},"
        f"{config.floater_min_contribution:g}"
    )


def build_ksplat_command(
    config: ExportConfig,
    source_ply: Path,
    dest_ksplat: Path,
) -> list[str]:
    """PLY (SH master) → cleaned ``.ksplat`` for the web viewer."""
    argv: list[str] = [config.splat_transform_bin, str(source_ply)]
    if config.filter_nan:
        argv.append("--filter-nan")
    if config.filter_floaters:
        argv.extend(["--filter-floaters", format_floater_args(config)])
    if config.web_sh_degree is not None:
        argv.extend(["--filter-harmonics", str(config.web_sh_degree)])
    argv.append(str(dest_ksplat))
    return argv


def build_thumbnail_command(
    ffmpeg: str,
    source: Path,
    dest: Path,
    *,
    max_edge: int,
) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-i",
        str(source),
        "-vf",
        f"scale='min({max_edge},iw)':-1",
        str(dest),
    ]


def find_latest_ply(candidates: list[Path]) -> Path | None:
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        return None
    return sorted(existing, key=lambda item: item.stat().st_mtime)[-1]
