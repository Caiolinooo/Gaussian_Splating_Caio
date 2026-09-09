"""Build the gsplat ``simple_trainer.py`` argv (tyro, underscore flags)."""

from __future__ import annotations

from pathlib import Path

from train.config import TrainConfig


def _int_list(flag: str, values: tuple[int, ...]) -> list[str]:
    return [flag, *[str(item) for item in values]]


def build_simple_trainer_command(
    config: TrainConfig,
    *,
    data_dir: Path,
    result_dir: Path,
    ckpt: Path | None = None,
) -> list[str]:
    """Reproduce the documented invocation:

    ``python simple_trainer.py default --data_dir … --data_factor 4 --result_dir …``
    """
    argv: list[str] = [
        config.python_bin,
        str(config.trainer_script),
        config.subcommand,
        "--data_dir",
        str(data_dir),
        "--data_factor",
        str(config.data_factor),
        "--result_dir",
        str(result_dir),
        "--max_steps",
        str(config.max_steps),
    ]
    argv.extend(_int_list("--save_steps", config.save_steps))
    argv.extend(_int_list("--eval_steps", config.eval_steps))
    argv.extend(_int_list("--ply_steps", config.ply_steps))
    if config.save_ply:
        argv.append("--save_ply")
    if config.disable_viewer:
        argv.append("--disable_viewer")
    if config.disable_video:
        argv.append("--disable_video")
    if ckpt is not None:
        # Official flag loads a .pt and runs evaluation (not mid-train resume).
        argv.extend(["--ckpt", str(ckpt)])
    argv.extend(config.extra_args)
    return argv


def artifact_step(path: Path) -> int:
    """Parse the numeric train step out of ``point_cloud_29999.ply`` / ``ckpt_6999_rank0.pt``.

    Lexical ``sorted()`` picks ``point_cloud_6999.ply`` over ``point_cloud_29999.ply``.
    """
    for part in reversed(path.stem.split("_")):
        if part.isdigit():
            return int(part)
    return -1


def latest_artifact(files: list[Path]) -> Path | None:
    if not files:
        return None
    return max(files, key=lambda path: (artifact_step(path), path.stat().st_mtime))


def latest_checkpoint(result_dir: Path) -> Path | None:
    ckpt_dir = result_dir / "ckpts"
    if not ckpt_dir.is_dir():
        return None
    return latest_artifact(list(ckpt_dir.glob("ckpt_*.pt")))


def latest_ply(result_dir: Path) -> Path | None:
    ply_dir = result_dir / "ply"
    if not ply_dir.is_dir():
        return None
    return latest_artifact(list(ply_dir.glob("point_cloud_*.ply")))
