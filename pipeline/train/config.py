"""gsplat ``simple_trainer.py`` configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Caminho rápido de avaliação L4: splat usável sem 7k steps.
EVAL_MIN_STEPS = 3_000
EVAL_DEFAULT_STEPS = 3_500
EVAL_MAX_STEPS = 4_000


def resolve_eval_train_steps(frame_count: int, configured_steps: int = EVAL_DEFAULT_STEPS) -> int:
    """Adapta só o default de avaliação. ``TRAIN_MAX_STEPS`` explícito (≠ 3500) fica."""
    if configured_steps != EVAL_DEFAULT_STEPS:
        return configured_steps
    if frame_count < 80:
        return EVAL_MIN_STEPS
    if frame_count > 220:
        return EVAL_MAX_STEPS
    return EVAL_DEFAULT_STEPS


@dataclass(frozen=True)
class TrainConfig:
    """Mirrors the public flags of nerfstudio-project/gsplat ``simple_trainer.py``."""

    python_bin: str = "python"
    trainer_script: Path = Path("simple_trainer.py")
    subcommand: str = "default"
    data_factor: int = 4
    max_steps: int = EVAL_DEFAULT_STEPS
    save_steps: tuple[int, ...] = (EVAL_DEFAULT_STEPS,)
    eval_steps: tuple[int, ...] = (EVAL_DEFAULT_STEPS,)
    ply_steps: tuple[int, ...] = (EVAL_DEFAULT_STEPS,)
    save_ply: bool = True
    disable_viewer: bool = True
    disable_video: bool = True
    extra_args: tuple[str, ...] = field(default_factory=lambda: ("--sh_degree", "2"))
    timeout_s: float | None = None

    def __post_init__(self) -> None:
        if self.data_factor < 1:
            raise ValueError("data_factor must be >= 1")
        if self.max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if self.subcommand not in {"default", "mcmc"}:
            raise ValueError("subcommand must be 'default' or 'mcmc'")
