"""Parse gsplat stdout and stats JSON (no GPU)."""

from __future__ import annotations

from pathlib import Path

from train.metrics import merge_metrics, parse_stats_json, parse_trainer_log

LOG = """
Step:  6999 {'mem': 3.1, 'ellipse_time': 120.0, 'num_GS': 850000}
Running evaluation...
PSNR: 27.450, SSIM: 0.8123, LPIPS: 0.145 Time: 0.012s/image Number of GS: 850000
"""


def test_parse_trainer_log_psnr_and_count() -> None:
    metrics = parse_trainer_log(LOG)
    assert metrics.psnr_val == 27.45
    assert metrics.ssim_val == 0.8123
    assert metrics.lpips_val == 0.145
    assert metrics.num_gaussians == 850000
    assert metrics.source == "log"


def test_parse_stats_json() -> None:
    metrics = parse_stats_json(
        {"psnr": 26.1, "ssim": 0.8, "lpips": 0.2, "num_GS": 1000, "ellipse_time": 0.01},
        path=Path("stats/val_step29999.json"),
    )
    assert metrics.psnr_val == 26.1
    assert metrics.num_gaussians == 1000
    assert metrics.last_step == 29999
    assert metrics.source == "stats_json"


def test_merge_prefers_json_psnr_and_injects_wall_time() -> None:
    merged = merge_metrics(
        parse_trainer_log("PSNR: 10.0 Number of GS: 1"),
        parse_stats_json({"psnr": 28.0, "num_GS": 5000}),
        duration_s=12.5,
    )
    assert merged.psnr_val == 28.0
    assert merged.num_gaussians == 5000
    assert merged.duration_s == 12.5
