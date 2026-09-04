"""Confidence score in ``[0, 1]`` for an auto-height scale factor.

The score is a **product of saturating terms** so any single failure mode
(no people, partial crop, high variance, …) pulls the result down. The
viewer treats low scores as "skip pre-apply, go to the tape measure"
(tasks.md §4 step 7 and §5 Fase 4).

Terms
-----
``c_frames``
    ``1 − exp(−n_valid / 5)``. 0 valid frames → 0; ~8 frames → 0.80;
    12+ → ~0.91. One lucky frame is never enough.

``c_body``
    Fraction of frames (among those with a person) where the full body is
    visible, raised to **1.2**. Partial crops therefore score *low*, not
    medium.

``c_vis``
    Mean critical-keypoint visibility of frames that contain a person,
    raised to 0.8. Occlusion / truncation show up here.

``c_var``
    ``exp(−(cv / 0.08)²)`` raised to 0.7, where ``cv`` is the coefficient
    of variation of inlier scene heights. 3 % cv stays high; 15 %+ collapses.

``c_multi``
    ``1 − 0.55 × (frames with >1 person) / n_frames``. Several people make
    it unclear whose height was typed in.

``c_depth``
    ``0.55`` when the ``DepthProvider`` is heuristic (no COLMAP depth);
    otherwise 1.

Final score: ``c_frames × c_body × c_vis × c_var × c_multi × c_depth``,
clamped to ``[0, 1]``.

Special cases
-------------
* No frame contained a person → **0** (do not pretend we calibrated).
* People seen but ``n_valid == 0`` (all partial / crouched / no depth) →
  still **0** for the *scale*, because we have no factor to trust. The
  warnings explain why.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from autocal.height_estimator import HeightEstimate
from autocal.stats import coefficient_of_variation

# Scale of the exponential frame-count saturator (frames).
FRAME_COUNT_TAU: float = 5.0
# cv at which variance term is e^{-1} before the 0.7 exponent.
VARIANCE_CV_SCALE: float = 0.08
# Multi-person penalty slope (1.0 would zero-out a fully crowded clip).
MULTI_PERSON_PENALTY: float = 0.55
# Confidence multiplier when Z/f_y were guessed.
HEURISTIC_DEPTH_FACTOR: float = 0.55


@dataclass(frozen=True, slots=True)
class ConfidenceInputs:
    """Features the scorer reads. Built from a ``HeightEstimate``."""

    n_frames_total: int
    n_frames_with_person: int
    n_valid: int
    full_body_ratio: float
    mean_visibility: float
    height_cv: float
    multi_person_ratio: float
    used_heuristic_depth: bool


def confidence_inputs_from_estimate(estimate: HeightEstimate) -> ConfidenceInputs:
    """Pack estimator diagnostics into the scorer's feature vector."""
    with_person = [obs for obs in estimate.observations if obs.n_persons > 0]
    if with_person:
        full_body_ratio = sum(1 for obs in with_person if obs.full_body_visible) / len(with_person)
        mean_visibility = sum(obs.mean_visibility for obs in with_person) / len(with_person)
    else:
        full_body_ratio = 0.0
        mean_visibility = 0.0
    return ConfidenceInputs(
        n_frames_total=len(estimate.observations),
        n_frames_with_person=len(with_person),
        n_valid=estimate.n_valid,
        full_body_ratio=full_body_ratio,
        mean_visibility=mean_visibility,
        height_cv=coefficient_of_variation(estimate.inlier_scene_heights),
        multi_person_ratio=estimate.multi_person_ratio,
        used_heuristic_depth=estimate.used_heuristic_depth,
    )


def score_confidence(inputs: ConfidenceInputs) -> float:
    """Return a score in ``[0, 1]``. Never raises."""
    if inputs.n_frames_with_person <= 0:
        return 0.0
    if inputs.n_valid <= 0:
        return 0.0

    c_frames = 1.0 - math.exp(-inputs.n_valid / FRAME_COUNT_TAU)
    c_body = max(0.0, min(1.0, inputs.full_body_ratio)) ** 1.2
    c_vis = max(0.0, min(1.0, inputs.mean_visibility)) ** 0.8
    c_var = math.exp(-((inputs.height_cv / VARIANCE_CV_SCALE) ** 2)) ** 0.7
    c_multi = max(0.0, 1.0 - MULTI_PERSON_PENALTY * max(0.0, min(1.0, inputs.multi_person_ratio)))
    c_depth = HEURISTIC_DEPTH_FACTOR if inputs.used_heuristic_depth else 1.0

    score = c_frames * c_body * c_vis * c_var * c_multi * c_depth
    return max(0.0, min(1.0, score))
