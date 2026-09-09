"""Defaults rápidos de avaliação L4 (3500 passos, adaptativo por frames)."""

from train.config import EVAL_DEFAULT_STEPS, TrainConfig, resolve_eval_train_steps


def test_train_config_defaults_are_eval_fast() -> None:
    cfg = TrainConfig()
    assert cfg.max_steps == EVAL_DEFAULT_STEPS == 3500
    assert cfg.save_steps == (3500,)
    assert cfg.eval_steps == (3500,)
    assert cfg.ply_steps == (3500,)
    assert cfg.disable_video is True


def test_resolve_eval_train_steps_adapts_only_default() -> None:
    assert resolve_eval_train_steps(40, 3500) == 3000
    assert resolve_eval_train_steps(150, 3500) == 3500
    assert resolve_eval_train_steps(400, 3500) == 4000
    assert resolve_eval_train_steps(40, 7000) == 7000
    assert resolve_eval_train_steps(400, 30_000) == 30_000
