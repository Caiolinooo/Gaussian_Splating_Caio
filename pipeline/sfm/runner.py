"""Execute the COLMAP SfM graph via an injected command runner."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from sfm.commands import build_sfm_pipeline_commands
from sfm.config import ColmapConfig, ColmapPaths, SourceKind
from sfm.errors import colmap_failed, no_reconstruction
from sfm.parse import ReconstructionSummary, count_input_images, summarize_reconstruction

LOGGER = logging.getLogger("pipeline.sfm")

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
class SfmResult:
    matcher: Literal["exhaustive", "sequential"]
    commands: tuple[tuple[str, ...], ...]
    summary: ReconstructionSummary
    model_dir: Path
    images_txt: Path | None
    log_text: str


_STEP_LABELS = (
    "Extraindo características (SIFT)…",
    "Correspondendo imagens…",
    "Reconstruindo a cena (mapper)…",
    "Exportando modelo texto…",
)


def run_sfm(
    config: ColmapConfig,
    paths: ColmapPaths,
    runner: CommandRunner,
    *,
    source_kind: SourceKind,
    progress: ProgressFn | None = None,
) -> SfmResult:
    paths.work_dir.mkdir(parents=True, exist_ok=True)
    paths.sparse_dir.mkdir(parents=True, exist_ok=True)

    matcher = config.resolve_matcher(source_kind)
    commands = build_sfm_pipeline_commands(config, paths, source_kind=source_kind)
    chunks: list[str] = []
    total = len(commands)

    for index, argv in enumerate(commands):
        label = _STEP_LABELS[index] if index < len(_STEP_LABELS) else argv[1]
        if progress is not None:
            progress(index / total, label)
        LOGGER.info("event=colmap_step step=%s argv=%s", argv[1], " ".join(argv))
        result = runner.run(argv, timeout_s=config.timeout_s)
        text = f"{result.stdout}\n{result.stderr}"
        chunks.append(text)
        if result.returncode != 0:
            # Converter is best-effort if the text model already exists.
            if argv[1] == "model_converter" and (paths.model_dir / "images.txt").is_file():
                LOGGER.info("event=colmap_converter_skipped reason=images_txt_exists")
                continue
            raise colmap_failed(argv[1], result.stderr.strip() or result.stdout.strip() or "nonzero")

    log_text = "\n".join(chunks)
    images_txt_path = paths.model_dir / "images.txt"
    images_txt = images_txt_path.read_text(encoding="utf-8", errors="replace") if images_txt_path.is_file() else None
    if images_txt is None and not (paths.model_dir / "images.bin").is_file():
        raise no_reconstruction("mapper produced no sparse/0 model")

    summary = summarize_reconstruction(
        images_txt=images_txt,
        log_text=log_text,
        input_image_count=count_input_images(paths.image_dir),
        min_registered_ratio=config.min_registered_ratio,
        min_registered_count=config.min_registered_count,
    )
    if progress is not None:
        progress(1.0, f"{summary.registered_count} imagens registradas.")
    LOGGER.info(
        "event=sfm_done matcher=%s registered=%s total=%s ratio=%.3f",
        matcher,
        summary.registered_count,
        summary.input_image_count,
        summary.ratio,
    )
    return SfmResult(
        matcher=matcher,
        commands=tuple(tuple(item) for item in commands),
        summary=summary,
        model_dir=paths.model_dir,
        images_txt=images_txt_path if images_txt_path.is_file() else None,
        log_text=log_text,
    )
