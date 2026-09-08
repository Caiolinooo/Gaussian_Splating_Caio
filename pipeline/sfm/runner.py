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
from sfm.errors import SfmError, colmap_failed, colmap_missing, no_reconstruction
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


# Falhas de qualidade que justificam a tentativa de resgate com SIFT mais sensível.
_RESCUABLE_CODES = frozenset({"FEW_REGISTERED", "NO_RECONSTRUCTION", "FEW_MATCHES"})

_RESCUE_PEAK_THRESHOLD = 0.004
_RESCUE_EDGE_THRESHOLD = 15.0
_RESCUE_MAX_NUM_FEATURES = 16384
_RESCUE_SEQUENTIAL_OVERLAP = 20


def _rescue_plan(config: ColmapConfig) -> ColmapConfig:
    """SIFT mais sensível + maior sobreposição sequencial, mesmo modo GPU/CPU."""
    return replace(
        config,
        sift_peak_threshold=_RESCUE_PEAK_THRESHOLD,
        sift_edge_threshold=_RESCUE_EDGE_THRESHOLD,
        sift_max_num_features=_RESCUE_MAX_NUM_FEATURES,
        sequential_overlap=max(config.sequential_overlap, _RESCUE_SEQUENTIAL_OVERLAP),
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

    matcher = config.resolve_matcher(source_kind, image_count=count_input_images(paths.image_dir))
    dialect = probe_cli_dialect(config, runner, matcher)

    plans = [config]
    cpu_tried = not config.use_gpu
    rescue_tried = False
    index = 0
    while index < len(plans):
        plan = plans[index]
        _clean_work_dir(paths)
        if index > 0 and progress is not None:
            progress(0.0, "Tentando novamente com parâmetros ajustados…")
        try:
            matcher, commands, log_text = _run_graph(
                plan,
                paths,
                runner,
                source_kind=source_kind,
                dialect=dialect,
                progress=progress,
            )
        except _StepFailed as exc:
            if plan.use_gpu and exc.step in _GPU_DEPENDENT_STEPS and not cpu_tried:
                cpu_tried = True
                plans.append(replace(config, use_gpu=False))
                LOGGER.warning(
                    "event=colmap_gpu_fallback failed_step=%s detail=%s",
                    exc.step,
                    exc.detail[:300],
                )
                _append_log(
                    paths,
                    f"\n===== GPU attempt failed at `{exc.step}`; retrying with use_gpu=0 =====\n",
                )
                if progress is not None:
                    progress(0.0, "SIFT em GPU falhou — tentando novamente em CPU…")
                index += 1
                continue
            raise colmap_failed(exc.step, exc.detail) from exc

        images_txt_path = paths.model_dir / "images.txt"
        images_txt = (
            images_txt_path.read_text(encoding="utf-8", errors="replace")
            if images_txt_path.is_file()
            else None
        )
        try:
            if images_txt is None and not (paths.model_dir / "images.bin").is_file():
                raise no_reconstruction("mapper produced no sparse/0 model")
            summary = summarize_reconstruction(
                images_txt=images_txt,
                log_text=log_text,
                input_image_count=count_input_images(paths.image_dir),
                min_registered_ratio=plan.min_registered_ratio,
                min_registered_count=plan.min_registered_count,
            )
        except SfmError as exc:
            if exc.code in _RESCUABLE_CODES and not rescue_tried:
                rescue_tried = True
                plans.append(_rescue_plan(plan))
                LOGGER.warning(
                    "event=colmap_rescue code=%s used_gpu=%s",
                    exc.code,
                    plan.use_gpu,
                )
                _append_log(
                    paths,
                    f"\n===== quality gate failed ({exc.code}); rescue attempt with relaxed SIFT =====\n",
                )
                if progress is not None:
                    progress(
                        0.0,
                        "Poucas imagens registradas — tentando resgate com SIFT mais sensível…",
                    )
                index += 1
                continue
            raise

        if progress is not None:
            progress(1.0, f"{summary.registered_count} imagens registradas.")
        LOGGER.info(
            "event=sfm_done matcher=%s registered=%s total=%s ratio=%.3f used_gpu=%s rescue=%s",
            matcher,
            summary.registered_count,
            summary.input_image_count,
            summary.ratio,
            plan.use_gpu,
            rescue_tried,
        )
        return SfmResult(
            matcher=matcher,
            commands=tuple(tuple(item) for item in commands),
            summary=summary,
            model_dir=paths.model_dir,
            images_txt=images_txt_path if images_txt_path.is_file() else None,
            log_text=log_text,
            log_path=paths.work_dir / LOG_FILENAME,
            used_gpu=plan.use_gpu,
        )

    # Unreachable: o laço sempre retorna ou levanta — mantém type-checkers felizes.
    raise AssertionError("run_sfm exhausted all plans without a result")
