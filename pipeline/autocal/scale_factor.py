"""Aggregate a metric scale factor from per-frame scene heights.

Definition
----------
COLMAP (and most SfM) reconstructions are defined up to a similarity. If the
user's real stature is ``H_real`` (metres) and the same person measures
``H_scene`` in reconstruction units, the unique scale that maps the scene
onto metres is

    s = H_real / H_scene

Applying ``s`` to the scene-root node makes 1 scene unit = 1 metre (when
``H_real`` is in metres). The live tape measure writes the same field with
``source = "manual"``.

Aggregation
-----------
Each inlier frame *i* votes ``s_i = H_real / H_scene,i`` with the frame
weight from the height estimator (visibility × posture). The reported factor
is the **weighted median** of ``{s_i}`` — robust to a few bad depths.

Error estimate
--------------
``errorEstimate`` is a robust 1-σ of the *scale samples* (same units as
``s``): ``1.4826 × MAD``. One sample uses a 20 % relative prior; two
samples use half the gap. The viewer can show ``s ± error`` and the
first-open prompt can refuse to pre-apply when ``error / s`` is large.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from autocal.stats import robust_sigma, weighted_median

# Relative 1-σ prior when only a single inlier frame exists.
SINGLE_SAMPLE_RELATIVE_ERROR: float = 0.20


@dataclass(frozen=True, slots=True)
class ScaleAggregation:
    """Weighted-median scale factor plus a robust error bar."""

    scale_factor: float
    error_estimate: float
    n_samples: int
    sample_scales: tuple[float, ...]


def aggregate_scale_factors(
    user_height_meters: float,
    scene_heights: Sequence[float],
    weights: Sequence[float] | None = None,
) -> ScaleAggregation:
    """Return ``s = H_real / H_scene`` aggregated across inlier frames.

    Raises
    ------
    ValueError
        If ``user_height_meters`` is not positive or ``scene_heights`` is empty.
        (The service never calls this on the "no person" path.)
    """
    if user_height_meters <= 0.0:
        raise ValueError("user_height_meters must be > 0")
    if not scene_heights:
        raise ValueError("scene_heights must be non-empty")

    scales: list[float] = []
    used_weights: list[float] = []
    raw_weights = list(weights) if weights is not None else [1.0] * len(scene_heights)
    if len(raw_weights) != len(scene_heights):
        raise ValueError("weights must match scene_heights")

    for height, weight in zip(scene_heights, raw_weights, strict=True):
        if height <= 1e-9:
            continue
        scales.append(user_height_meters / height)
        used_weights.append(weight if weight > 0.0 else 0.0)

    if not scales:
        raise ValueError("all scene_heights were non-positive")

    scale = weighted_median(scales, used_weights)
    error = _scale_error(scales, scale)
    return ScaleAggregation(
        scale_factor=scale,
        error_estimate=error,
        n_samples=len(scales),
        sample_scales=tuple(scales),
    )


def _scale_error(scales: Sequence[float], scale: float) -> float:
    if len(scales) == 1:
        return abs(scale) * SINGLE_SAMPLE_RELATIVE_ERROR
    if len(scales) == 2:
        return abs(scales[0] - scales[1]) / 2.0
    return robust_sigma(scales)
