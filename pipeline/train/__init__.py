"""gsplat training wrapper: command generation + metric collection."""

from train.commands import build_simple_trainer_command, latest_checkpoint, latest_ply
from train.config import TrainConfig, resolve_eval_train_steps
from train.errors import TrainError
from train.metrics import TrainMetrics, parse_stats_json, parse_trainer_log
from train.runner import TrainResult, run_training

__all__ = [
    "TrainConfig",
    "resolve_eval_train_steps",
    "TrainError",
    "TrainMetrics",
    "TrainResult",
    "build_simple_trainer_command",
    "latest_checkpoint",
    "latest_ply",
    "parse_stats_json",
    "parse_trainer_log",
    "run_training",
]
