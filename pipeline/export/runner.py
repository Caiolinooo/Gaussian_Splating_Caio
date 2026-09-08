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


def _looks_like_missing_binary(detail: str, binary: str) -> bool:
    text = f"{detail} {binary}".lower()
    # Tokens de "binário ausente" — inclusive quando a resolução cai no `npx`
    # e o npm não acha o pacote executável (E404 / could not determine executable).
    return any(
        token in text
        for token in (
            "not found",
            "não encontrado",
            "cannot find",
            "no such file",
            "could not determine executable",
            "npm error code e404",
        )
    )


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
    try:
        converted = runner.run(ksplat_argv, timeout_s=config.timeout_s)
    except FileNotFoundError:
        LOGGER.info("event=splat_transform_missing bin=%s", config.splat_transform_bin)
        converted = None
    if converted is not None and (converted.returncode != 0 or not web.is_file()):
        detail = converted.stderr.strip() or converted.stdout.strip() or "ksplat missing"
        missing = _looks_like_missing_binary(detail, config.splat_transform_bin)
        if missing:
            LOGGER.info("event=splat_transform_skipped detail=%s", detail)
        else:
            raise transform_failed(detail)
    elif converted is None:
        LOGGER.info("event=splat_transform_skipped reason=binary_missing")

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
        try:
            shot = runner.run(argv, timeout_s=config.timeout_s)
        except FileNotFoundError:
            LOGGER.info("event=thumbnail_skipped reason=ffmpeg_missing")
            shot = None
        if shot is not None and shot.returncode == 0 and dest.is_file():
            thumbnail = dest
        elif dest.is_file():
            thumbnail = dest
        elif shot is not None:
            LOGGER.info("event=thumbnail_failed detail=%s", shot.stderr.strip())
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
