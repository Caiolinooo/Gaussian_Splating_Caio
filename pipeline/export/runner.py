"""Copy master PLY (SH), convert to .ksplat, write a preview thumbnail."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from export.commands import build_ksplat_command, build_thumbnail_command
from export.config import ExportConfig
from export.errors import missing_ply, thumbnail_failed, transform_failed
from export.thumbnails import pick_thumbnail_source

LOGGER = logging.getLogger("pipeline.export")

ProgressFn = Callable[[float, str], None]


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_s: float | None = None,
    ) -> CommandResult: ...


@dataclass(frozen=True)
class ExportResult:
    master_ply: Path
    web_ksplat: Path
    thumbnail: Path | None
    ksplat_argv: tuple[str, ...]
    thumbnail_argv: tuple[str, ...] | None


def _copy_master(source_ply: Path, dest_ply: Path) -> Path:
    dest_ply.parent.mkdir(parents=True, exist_ok=True)
    if source_ply.resolve() != dest_ply.resolve():
        shutil.copy2(source_ply, dest_ply)
    return dest_ply


def run_export(
    config: ExportConfig,
    *,
    source_ply: Path,
    export_dir: Path,
    runner: CommandRunner,
    render_dir: Path | None = None,
    frames_dir: Path | None = None,
    progress: ProgressFn | None = None,
) -> ExportResult:
    if not source_ply.is_file():
        raise missing_ply(str(source_ply))
    export_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir = export_dir / "thumbnails"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    master = export_dir / "master.ply"
    web = export_dir / "scene.ksplat"

    if progress is not None:
        progress(0.1, "Copiando .ply mestre (SH)…")
    _copy_master(source_ply, master)
    LOGGER.info("event=export_ply_copied src=%s dest=%s", source_ply, master)

    ksplat_argv = build_ksplat_command(config, master, web)
    if progress is not None:
        progress(0.4, "Convertendo para .ksplat e limpando floaters…")
    LOGGER.info("event=splat_transform_start argv=%s", " ".join(ksplat_argv))
    converted = runner.run(ksplat_argv, timeout_s=config.timeout_s)
    if converted.returncode != 0 or not web.is_file():
        raise transform_failed(converted.stderr.strip() or converted.stdout.strip() or "ksplat missing")

    thumbnail: Path | None = None
    thumbnail_argv: tuple[str, ...] | None = None
    source = pick_thumbnail_source(render_dir=render_dir, frames_dir=frames_dir)
    if source is not None:
        dest = thumbs_dir / config.thumbnail_name
        argv = build_thumbnail_command(
            config.ffmpeg_bin,
            source,
            dest,
            max_edge=config.thumbnail_max_edge,
        )
        thumbnail_argv = tuple(argv)
        if progress is not None:
            progress(0.8, "Gerando miniatura…")
        shot = runner.run(argv, timeout_s=config.timeout_s)
        if shot.returncode == 0 and dest.is_file():
            thumbnail = dest
        else:
            LOGGER.info("event=thumbnail_failed detail=%s", shot.stderr.strip())
            if dest.is_file():
                thumbnail = dest
            else:
                raise thumbnail_failed(shot.stderr.strip() or "thumbnail missing")

    if progress is not None:
        progress(1.0, "Exportação concluída.")
    LOGGER.info("event=export_done ply=%s ksplat=%s thumb=%s", master, web, thumbnail)
    return ExportResult(
        master_ply=master,
        web_ksplat=web,
        thumbnail=thumbnail,
        ksplat_argv=tuple(ksplat_argv),
        thumbnail_argv=thumbnail_argv,
    )
