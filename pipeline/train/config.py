"""gsplat ``simple_trainer.py`` configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Qualidade L4 (24 GB): paper gsplat inria-30k + SH3 + data_factor 2.
QUALITY_MIN_STEPS = 15_000
QUALITY_DEFAULT_STEPS = 30_000
QUALITY_MAX_STEPS = 30_000
EVAL_MIN_STEPS = QUALITY_MIN_STEPS
EVAL_DEFAULT_STEPS = QUALITY_DEFAULT_STEPS
EVAL_MAX_STEPS = QUALITY_MAX_STEPS


def resolve_eval_train_steps(frame_count: int, configured_steps: int = QUALITY_DEFAULT_STEPS) -> int:
    """Adapta o default de qualidade. ``TRAIN_MAX_STEPS`` explícito (≠ 30000) fica."""
    if configured_steps != QUALITY_DEFAULT_STEPS:
        return configured_steps
    if frame_count < 80:
        return QUALITY_MIN_STEPS
    return QUALITY_DEFAULT_STEPS


@dataclass(frozen=True)
class TrainConfig:
    """Mirrors the public flags of nerfstudio-project/gsplat ``simple_trainer.py``."""

    python_bin: str = "python"
    trainer_script: Path = Path("simple_trainer.py")
    subcommand: str = "default"
    data_factor: int = 2
    max_steps: int = QUALITY_DEFAULT_STEPS
    save_steps: tuple[int, ...] = (15_000, QUALITY_DEFAULT_STEPS)
    eval_steps: tuple[int, ...] = (QUALITY_DEFAULT_STEPS,)
    ply_steps: tuple[int, ...] = (15_000, QUALITY_DEFAULT_STEPS)
    save_ply: bool = True
    disable_viewer: bool = True
    disable_video: bool = True
    extra_args: tuple[str, ...] = field(
        default_factory=lambda: (
            "--sh_degree",
            "3",
            "--scale_reg",
            "0.01",
            "--opacity_reg",
            "0.01",
        )
    )
    timeout_s: float | None = None

    def __post_init__(self) -> None:
        if self.data_factor < 1:
            raise ValueError("data_factor must be >= 1")
        if self.max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        if self.subcommand not in {"default", "mcmc"}:
            raise ValueError("subcommand must be 'default' or 'mcmc'")
