"""Defaults de qualidade L4 (15k passos, data_factor=2, SH 3, scale_reg)."""

from pathlib import Path

from train.config import (
    QUALITY_DEFAULT_STEPS,
    TrainConfig,
    canonicalize_extra_args,
    resolve_eval_train_steps,
)
from train.errors import trainer_failed
from train.runner import ensure_data_factor_images, persist_trainer_log


def test_train_config_defaults_are_quality() -> None:
    cfg = TrainConfig()
    assert cfg.max_steps == QUALITY_DEFAULT_STEPS == 30_000
    assert cfg.data_factor == 2
    assert cfg.save_steps == (15_000, 30_000)
    assert cfg.ply_steps == (15_000, 30_000)
    assert cfg.disable_video is True
    assert "--scale_reg" in cfg.extra_args


def test_resolve_eval_train_steps_adapts_only_default() -> None:
    assert resolve_eval_train_steps(40, 30_000) == 15_000
    assert resolve_eval_train_steps(150, 30_000) == 30_000
    assert resolve_eval_train_steps(400, 30_000) == 30_000
    assert resolve_eval_train_steps(40, 7000) == 7000
    assert resolve_eval_train_steps(400, 12_000) == 12_000


def test_canonicalize_extra_args_rewrites_legacy_normalize_value() -> None:
    legacy = ("--sh_degree", "3", "--normalize_world_space", "False")
    assert "--no-normalize-world-space" in canonicalize_extra_args(legacy)
    assert "False" not in canonicalize_extra_args(legacy)
    assert canonicalize_extra_args(("--normalize_world_space", "True")) == ()
    assert canonicalize_extra_args(("--no-normalize-world-space",)) == ("--no-normalize-world-space",)
    assert canonicalize_extra_args(("--normalize_world_space", "--sh_degree")) == (
        "--normalize_world_space",
        "--sh_degree",
    )


def test_train_config_canonicalizes_persisted_legacy_args() -> None:
    cfg = TrainConfig(extra_args=("--sh_degree", "3", "--normalize_world_space", "False"))
    assert cfg.extra_args == ("--sh_degree", "3", "--no-normalize-world-space")


def test_ensure_data_factor_images_symlinks_when_missing(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "frame.jpg").write_bytes(b"x")
    dest = ensure_data_factor_images(tmp_path, 4)
    assert dest is not None
    assert dest.exists()
    assert (dest / "frame.jpg").is_file()
    assert ensure_data_factor_images(tmp_path, 4) == dest


def test_ensure_data_factor_images_skips_factor_one(tmp_path: Path) -> None:
    (tmp_path / "images").mkdir()
    assert ensure_data_factor_images(tmp_path, 1) is None
    assert not (tmp_path / "images_1").exists()


def test_persist_trainer_log_writes_argv_and_stderr(tmp_path: Path) -> None:
    extra = tmp_path / "logs"
    text = persist_trainer_log(
        tmp_path / "train",
        argv=["/home/caio/gaussian-splating/.venv/bin/python", "simple_trainer.py"],
        returncode=1,
        stdout="",
        stderr="ModuleNotFoundError: No module named 'tyro'",
        extra_log_dir=extra,
    )
    assert "tyro" in text
    body = (tmp_path / "train" / "train.log").read_text(encoding="utf-8")
    assert ".venv/bin/python" in body
    assert "No module named 'tyro'" in body
    assert (extra / "train.log").read_text(encoding="utf-8") == body


def test_trainer_failed_hints_tyro_and_cuda() -> None:
    tyro = trainer_failed("ModuleNotFoundError: No module named 'tyro'")
    assert tyro.code == "TRAINER_FAILED"
    assert "tyro" in (tyro.user_message or "").lower()
    cuda = trainer_failed("RuntimeError: CUDA out of memory")
    assert "CUDA" in (cuda.user_message or "")
