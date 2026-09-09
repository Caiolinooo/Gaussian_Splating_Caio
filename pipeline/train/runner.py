"""Run gsplat ``simple_trainer.py`` through an injected command runner."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from train.commands import build_simple_trainer_command, latest_checkpoint, latest_ply
from train.config import TrainConfig
from train.errors import missing_dataset, trainer_failed
from train.metrics import TrainMetrics, load_latest_val_stats, merge_metrics, parse_trainer_log

LOGGER = logging.getLogger("pipeline.train")

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
class TrainResult:
    argv: tuple[str, ...]
    metrics: TrainMetrics
    result_dir: Path
    ply_path: Path | None
    ckpt_path: Path | None
    log_text: str


def ensure_data_factor_images(data_dir: Path, factor: int) -> Path | None:
    """gsplat Parser exige ``images_{factor}`` quando ``factor > 1``.

    O dataset do job só tem ``images/`` (frames do ingest). Sem a pasta
    sufixada o trainer cai imediatamente. Um symlink para ``images`` deixa o
    examples/datasets/colmap.py criar ``images_{factor}_png`` (JPEG) ou
    reutilizar os frames.
    """
    if factor <= 1:
        return None
    images = data_dir / "images"
    dest = data_dir / f"images_{factor}"
    if dest.exists() or dest.is_symlink():
        return dest
    if not images.exists():
        return None
    dest.symlink_to(images, target_is_directory=True)
    LOGGER.info("event=train_images_factor src=%s dest=%s", images, dest)
    return dest


def persist_trainer_log(
    result_dir: Path,
    *,
    argv: Sequence[str],
    returncode: int,
    stdout: str,
    stderr: str,
    extra_log_dir: Path | None = None,
) -> str:
    """Write stdout/stderr even when the trainer exits non-zero (tyro/CUDA)."""
    result_dir.mkdir(parents=True, exist_ok=True)
    text = (
        f"argv: {' '.join(argv)}\n"
        f"returncode: {returncode}\n"
        f"--- stdout ---\n{stdout}\n"
        f"--- stderr ---\n{stderr}\n"
    )
    dest = result_dir / "train.log"
    dest.write_text(text, encoding="utf-8")
    if extra_log_dir is not None:
        extra_log_dir.mkdir(parents=True, exist_ok=True)
        (extra_log_dir / "train.log").write_text(text, encoding="utf-8")
    LOGGER.info("event=train_log path=%s returncode=%s", dest, returncode)
    return f"{stdout}\n{stderr}"


def run_training(
    config: TrainConfig,
    *,
    data_dir: Path,
    result_dir: Path,
    runner: CommandRunner,
    progress: ProgressFn | None = None,
    ckpt: Path | None = None,
    extra_log_dir: Path | None = None,
) -> TrainResult:
    if not data_dir.exists():
        raise missing_dataset(str(data_dir))
    ensure_data_factor_images(data_dir, config.data_factor)
    result_dir.mkdir(parents=True, exist_ok=True)
    argv = build_simple_trainer_command(
        config,
        data_dir=data_dir,
        result_dir=result_dir,
        ckpt=ckpt,
    )
    if progress is not None:
        progress(0.02, "Iniciando treino 3DGS…")
    LOGGER.info("event=gsplat_start argv=%s", " ".join(argv))
    started = time.monotonic()
    executed = runner.run(argv, timeout_s=config.timeout_s)
    duration = time.monotonic() - started
    log_text = persist_trainer_log(
        result_dir,
        argv=argv,
        returncode=executed.returncode,
        stdout=executed.stdout,
        stderr=executed.stderr,
        extra_log_dir=extra_log_dir,
    )
    if executed.returncode != 0:
        raise trainer_failed(executed.stderr.strip() or executed.stdout.strip() or "nonzero")

    metrics = merge_metrics(
        parse_trainer_log(log_text),
        load_latest_val_stats(result_dir),
        duration_s=duration,
    )
    ply_path = latest_ply(result_dir)
    ckpt_path = latest_checkpoint(result_dir)
    if progress is not None:
        psnr = f"{metrics.psnr_val:.2f}" if metrics.psnr_val is not None else "n/d"
        progress(1.0, f"Treino concluído (PSNR val {psnr}).")
    LOGGER.info(
        "event=gsplat_done psnr=%s num_gs=%s duration_s=%.1f ply=%s",
        metrics.psnr_val,
        metrics.num_gaussians,
        duration,
        ply_path,
    )
    return TrainResult(
        argv=tuple(argv),
        metrics=metrics,
        result_dir=result_dir,
        ply_path=ply_path,
        ckpt_path=ckpt_path,
        log_text=log_text,
    )
