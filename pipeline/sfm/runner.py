"""Execute the COLMAP SfM graph via an injected command runner."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from sfm.commands import ColmapCliDialect, build_sfm_pipeline_commands
from sfm.config import ColmapConfig, ColmapPaths, SourceKind
from sfm.errors import colmap_failed, colmap_missing, no_reconstruction
from sfm.parse import ReconstructionSummary, count_input_images, summarize_reconstruction

LOGGER = logging.getLogger("pipeline.sfm")

ProgressFn = Callable[[float, str], None]

LOG_FILENAME = "colmap.log"

# Steps whose CLI flags depend on a working GPU/GL stack. A nonzero exit in one
# of these with ``use_gpu=1`` is retried once in CPU mode (headless-safe).
_GPU_DEPENDENT_STEPS = frozenset({"feature_extractor", "exhaustive_matcher", "sequential_matcher"})


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


class _StepFailed(Exception):
    """Nonzero COLMAP exit — eligible for the GPU→CPU retry, unlike a missing binary."""

    def __init__(self, step: str, detail: str) -> None:
        super().__init__(detail)
        self.step = step
        self.detail = detail


@dataclass(frozen=True)
class SfmResult:
    matcher: Literal["exhaustive", "sequential"]
    commands: tuple[tuple[str, ...], ...]
    summary: ReconstructionSummary
    model_dir: Path
    images_txt: Path | None
    log_text: str
    log_path: Path
    used_gpu: bool


_STEP_LABELS = (
    "Extraindo características (SIFT)…",
    "Correspondendo imagens…",
    "Reconstruindo a cena (mapper)…",
    "Exportando modelo texto…",
)


def _append_log(paths: ColmapPaths, text: str) -> None:
    log_path = paths.work_dir / LOG_FILENAME
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def _clean_work_dir(paths: ColmapPaths) -> None:
    """Drop partial state from previous attempts — the SfM stage is atomic."""
    for suffix in ("", "-wal", "-shm"):
        paths.database.with_name(paths.database.name + suffix).unlink(missing_ok=True)
    if paths.sparse_dir.exists():
        shutil.rmtree(paths.sparse_dir)
    paths.sparse_dir.mkdir(parents=True, exist_ok=True)


def _help_text(config: ColmapConfig, runner: CommandRunner, command: str) -> str:
    """``colmap <command> -h`` — texto de ajuda ou "" quando indisponível."""
    try:
        result = runner.run([config.colmap_bin, command, "-h"], timeout_s=15.0)
    except FileNotFoundError as exc:
        raise colmap_missing(config.colmap_bin) from exc
    except OSError as exc:
        if getattr(exc, "errno", None) in {2, 3} or getattr(exc, "winerror", None) == 2:
            raise colmap_missing(config.colmap_bin) from exc
        return ""
    if result.returncode != 0:
        return ""
    return f"{result.stdout}\n{result.stderr}"


def _pick_flag(help_text: str, candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in help_text:
            return candidate
    return None


def probe_cli_dialect(
    config: ColmapConfig,
    runner: CommandRunner,
    matcher: Literal["exhaustive", "sequential"],
) -> ColmapCliDialect:
    """Detecta os nomes de flag de GPU do binário instalado (3.x legado vs 4.x)."""
    extraction_help = _help_text(config, runner, "feature_extractor")
    matching_help = _help_text(config, runner, f"{matcher}_matcher")
    dialect = ColmapCliDialect(
        extraction_gpu_flag=_pick_flag(
            extraction_help, ("FeatureExtraction.use_gpu", "SiftExtraction.use_gpu")
        ),
        matching_gpu_flag=_pick_flag(
            matching_help, ("FeatureMatching.use_gpu", "SiftMatching.use_gpu")
        ),
    )
    LOGGER.info(
        "event=colmap_dialect extraction_flag=%s matching_flag=%s",
        dialect.extraction_gpu_flag,
        dialect.matching_gpu_flag,
    )
    return dialect


def _run_graph(
    config: ColmapConfig,
    paths: ColmapPaths,
    runner: CommandRunner,
    *,
    source_kind: SourceKind,
    dialect: ColmapCliDialect,
    progress: ProgressFn | None,
) -> tuple[Literal["exhaustive", "sequential"], list[list[str]], str]:
    matcher = config.resolve_matcher(source_kind)
    commands = build_sfm_pipeline_commands(config, paths, source_kind=source_kind, dialect=dialect)
    chunks: list[str] = []
    total = len(commands)

    for index, argv in enumerate(commands):
        label = _STEP_LABELS[index] if index < len(_STEP_LABELS) else argv[1]
        if progress is not None:
            progress(index / total, label)
        LOGGER.info("event=colmap_step step=%s argv=%s", argv[1], " ".join(argv))
        try:
            result = runner.run(argv, timeout_s=config.timeout_s)
        except FileNotFoundError as exc:
            raise colmap_missing(str(argv[0])) from exc
        except OSError as exc:
            if getattr(exc, "errno", None) in {2, 3} or getattr(exc, "winerror", None) == 2:
                raise colmap_missing(str(argv[0])) from exc
            raise
        text = f"{result.stdout}\n{result.stderr}"
        chunks.append(text)
        stamp = datetime.now(UTC).isoformat()
        _append_log(paths, f"\n===== {stamp} $ {' '.join(argv)} =====\n{text}\n")
        if result.returncode != 0:
            # Converter is best-effort if the text model already exists.
            if argv[1] == "model_converter" and (paths.model_dir / "images.txt").is_file():
                LOGGER.info("event=colmap_converter_skipped reason=images_txt_exists")
                continue
            raise _StepFailed(argv[1], result.stderr.strip() or result.stdout.strip() or "nonzero")
    return matcher, commands, "\n".join(chunks)


def run_sfm(
    config: ColmapConfig,
    paths: ColmapPaths,
    runner: CommandRunner,
    *,
    source_kind: SourceKind,
    progress: ProgressFn | None = None,
) -> SfmResult:
    paths.work_dir.mkdir(parents=True, exist_ok=True)

    matcher = config.resolve_matcher(source_kind, image_count=count_input_images(paths.image_dir))
    dialect = probe_cli_dialect(config, runner, matcher)

    attempts = [config]
    if config.use_gpu:
        attempts.append(replace(config, use_gpu=False))

    last_failure: _StepFailed | None = None
    for attempt_index, attempt_config in enumerate(attempts):
        _clean_work_dir(paths)
        if attempt_index > 0 and last_failure is not None:
            LOGGER.warning(
                "event=colmap_gpu_fallback failed_step=%s detail=%s",
                last_failure.step,
                last_failure.detail[:300],
            )
            _append_log(
                paths,
                f"\n===== GPU attempt failed at `{last_failure.step}`; retrying with use_gpu=0 =====\n",
            )
            if progress is not None:
                progress(0.0, "SIFT em GPU falhou — tentando novamente em CPU…")
        try:
            matcher, commands, log_text = _run_graph(
                attempt_config,
                paths,
                runner,
                source_kind=source_kind,
                dialect=dialect,
                progress=progress,
            )
        except _StepFailed as exc:
            if attempt_config.use_gpu and exc.step in _GPU_DEPENDENT_STEPS:
                last_failure = exc
                continue
            raise colmap_failed(exc.step, exc.detail) from exc

        images_txt_path = paths.model_dir / "images.txt"
        images_txt = (
            images_txt_path.read_text(encoding="utf-8", errors="replace")
            if images_txt_path.is_file()
            else None
        )
        if images_txt is None and not (paths.model_dir / "images.bin").is_file():
            raise no_reconstruction("mapper produced no sparse/0 model")

        summary = summarize_reconstruction(
            images_txt=images_txt,
            log_text=log_text,
            input_image_count=count_input_images(paths.image_dir),
            min_registered_ratio=attempt_config.min_registered_ratio,
            min_registered_count=attempt_config.min_registered_count,
        )
        if progress is not None:
            progress(1.0, f"{summary.registered_count} imagens registradas.")
        LOGGER.info(
            "event=sfm_done matcher=%s registered=%s total=%s ratio=%.3f used_gpu=%s",
            matcher,
            summary.registered_count,
            summary.input_image_count,
            summary.ratio,
            attempt_config.use_gpu,
        )
        return SfmResult(
            matcher=matcher,
            commands=tuple(tuple(item) for item in commands),
            summary=summary,
            model_dir=paths.model_dir,
            images_txt=images_txt_path if images_txt_path.is_file() else None,
            log_text=log_text,
            log_path=paths.work_dir / LOG_FILENAME,
            used_gpu=attempt_config.use_gpu,
        )

    # Unreachable without a GPU retryable failure, but keeps type-checkers happy.
    assert last_failure is not None
    raise colmap_failed(last_failure.step, last_failure.detail)
