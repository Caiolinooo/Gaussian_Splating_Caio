"""Robust statistics used by height aggregation (no numpy).

All estimators here are deterministic and work on small per-job samples
(tens to hundreds of frames), so the stdlib is enough.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence

# Conversion from MAD to a Gaussian-equivalent standard deviation.
MAD_TO_SIGMA: float = 1.4826


def iqr_bounds(values: Sequence[float], *, k: float = 1.5) -> tuple[float, float]:
    """Return ``(lo, hi)`` Tukey fences.

    With fewer than 4 samples the fences collapse to ``(min, max)`` so we do
    not discard the only evidence we have.
    """
    if not values:
        raise ValueError("iqr_bounds requires at least one value")
    if len(values) < 4:
        return (min(values), max(values))
    q1, _q2, q3 = statistics.quantiles(list(values), n=4, method="inclusive")
    iqr = q3 - q1
    return (q1 - k * iqr, q3 + k * iqr)


def iqr_inlier_mask(values: Sequence[float], *, k: float = 1.5) -> list[bool]:
    """True where ``values[i]`` lies inside the Tukey fences."""
    lo, hi = iqr_bounds(values, k=k)
    return [lo <= v <= hi for v in values]


def weighted_median(values: Sequence[float], weights: Sequence[float]) -> float:
    """Weighted median: smallest ``v`` whose cumulative weight reaches 50%.

    Negative weights are treated as 0. If every weight is 0, falls back to the
    unweighted median. When the cumulative weight lands exactly on the halfway
    point, the two neighbouring values are averaged (even-n behaviour).
    """
    if len(values) != len(weights):
        raise ValueError("values and weights must have the same length")
    if not values:
        raise ValueError("weighted_median requires at least one value")

    pairs = sorted(zip(values, weights, strict=True), key=lambda item: item[0])
    total = sum(max(weight, 0.0) for _value, weight in pairs)
    if total <= 0.0:
        return float(statistics.median(values))

    half = total / 2.0
    accumulated = 0.0
    for index, (value, weight) in enumerate(pairs):
        accumulated += max(weight, 0.0)
        if accumulated >= half:
            if abs(accumulated - half) < 1e-12 and index + 1 < len(pairs):
                return 0.5 * (value + pairs[index + 1][0])
            return float(value)
    return float(pairs[-1][0])


def coefficient_of_variation(values: Sequence[float]) -> float:
    """``stdev / |mean|``. Returns 0 for a single sample or a near-zero mean."""
    if len(values) < 2:
        return 0.0
    mean = statistics.fmean(values)
    if abs(mean) < 1e-12:
        return 0.0
    return float(statistics.stdev(values) / abs(mean))


def robust_sigma(values: Sequence[float]) -> float:
    """Gaussian-equivalent scale: ``1.4826 * median(|x - median(x)|)``."""
    if len(values) < 2:
        return 0.0
    centre = statistics.median(values)
    mad = statistics.median([abs(value - centre) for value in values])
    return float(MAD_TO_SIGMA * mad)
