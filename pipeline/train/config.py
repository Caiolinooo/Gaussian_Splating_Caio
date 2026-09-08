"""gsplat ``simple_trainer.py`` configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TrainConfig:
    """Mirrors the public flags of nerfstudio-project/gsplat ``simple_trainer.py``."""

    python_bin: str = "python"
    trainer_script: Path = Path("simple_trainer.py")
    subcommand: str = "default"
    data_factor: int = 4
    max_steps: int = 7_000
    save_steps: tuple[int, ...] = (7_000,)
    eval_steps: tuple[int, ...] = (7_000,)
    ply_steps: tuple[int, ...] = (7_000,)
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
