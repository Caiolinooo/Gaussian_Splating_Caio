"""Collect PSNR / gaussian count / wall time from gsplat logs and stats JSON."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PSNR_LINE = re.compile(
    r"PSNR:\s*(?P<psnr>[-+]?\d+(?:\.\d+)?)"
    r"(?:.*SSIM:\s*(?P<ssim>[-+]?\d+(?:\.\d+)?))?"
    r"(?:.*LPIPS:\s*(?P<lpips>[-+]?\d+(?:\.\d+)?))?"
    r"(?:.*Number of GS:\s*(?P<gs>\d+))?",
    re.IGNORECASE,
)
_NUM_GS = re.compile(r"Number of GS:\s*(?P<gs>\d+)", re.IGNORECASE)
_STEP_STATS = re.compile(r"Step:\s*(?P<step>\d+).*num_GS['\"]?:\s*(?P<gs>\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class TrainMetrics:
    psnr_val: float | None
    ssim_val: float | None
    lpips_val: float | None
    num_gaussians: int | None
    duration_s: float | None
    last_step: int | None
    stats_path: str | None
    source: str


def parse_trainer_log(log_text: str) -> TrainMetrics:
    psnr: float | None = None
    ssim: float | None = None
    lpips: float | None = None
    gs: int | None = None
    last_step: int | None = None
    for match in _PSNR_LINE.finditer(log_text):
        psnr = float(match.group("psnr"))
        if match.group("ssim"):
            ssim = float(match.group("ssim"))
        if match.group("lpips"):
            lpips = float(match.group("lpips"))
        if match.group("gs"):
            gs = int(match.group("gs"))
    if gs is None:
        gs_match = list(_NUM_GS.finditer(log_text))
        if gs_match:
            gs = int(gs_match[-1].group("gs"))
    step_match = list(_STEP_STATS.finditer(log_text))
    if step_match:
        last_step = int(step_match[-1].group("step"))
        if gs is None:
            gs = int(step_match[-1].group("gs"))
    return TrainMetrics(
        psnr_val=psnr,
        ssim_val=ssim,
        lpips_val=lpips,
        num_gaussians=gs,
        duration_s=None,
        last_step=last_step,
        stats_path=None,
        source="log",
    )


def parse_stats_json(payload: dict[str, Any], *, path: Path | None = None) -> TrainMetrics:
    psnr = payload.get("psnr")
    ssim = payload.get("ssim")
    lpips = payload.get("lpips")
    gs = payload.get("num_GS", payload.get("num_gaussians"))
    duration = payload.get("ellipse_time")
    return TrainMetrics(
        psnr_val=float(psnr) if psnr is not None else None,
        ssim_val=float(ssim) if ssim is not None else None,
        lpips_val=float(lpips) if lpips is not None else None,
        num_gaussians=int(gs) if gs is not None else None,
        duration_s=float(duration) if duration is not None else None,
        last_step=_step_from_stats_name(path),
        stats_path=str(path) if path is not None else None,
        source="stats_json",
    )


def _step_from_stats_name(path: Path | None) -> int | None:
    if path is None:
        return None
    match = re.search(r"step(\d+)", path.name)
    return int(match.group(1)) if match else None


def load_latest_val_stats(result_dir: Path) -> TrainMetrics | None:
    stats_dir = result_dir / "stats"
    if not stats_dir.is_dir():
        return None
    candidates = sorted(stats_dir.glob("val_step*.json"))
    if not candidates:
        candidates = sorted(stats_dir.glob("*.json"))
    if not candidates:
        return None
    path = candidates[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return parse_stats_json(payload, path=path)


def merge_metrics(*parts: TrainMetrics | None, duration_s: float | None = None) -> TrainMetrics:
    """Prefer JSON stats for PSNR/count; keep the last non-null field."""
    merged = TrainMetrics(
        psnr_val=None,
        ssim_val=None,
        lpips_val=None,
        num_gaussians=None,
        duration_s=duration_s,
        last_step=None,
        stats_path=None,
        source="merged",
    )
    for part in parts:
        if part is None:
            continue
        merged = TrainMetrics(
            psnr_val=_prefer(part.psnr_val, merged.psnr_val),
            ssim_val=_prefer(part.ssim_val, merged.ssim_val),
            lpips_val=_prefer(part.lpips_val, merged.lpips_val),
            num_gaussians=_prefer(part.num_gaussians, merged.num_gaussians),
            duration_s=_prefer(part.duration_s, merged.duration_s) if duration_s is None else duration_s,
            last_step=_prefer(part.last_step, merged.last_step),
            stats_path=_prefer(part.stats_path, merged.stats_path),
            source="merged",
        )
    return merged


def _prefer(new: Any, old: Any) -> Any:
    return new if new is not None else old
