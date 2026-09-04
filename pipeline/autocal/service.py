"""Orchestrate auto-calibration: frames + user height → ``CalibrationResult``.

Integration contract (jobs / scene JSON)
========================================

Who calls this
--------------
``pipeline/jobs`` (stage ``autocal`` in the state machine
``queued → extracting → sfm → training → exporting → autocal → done|error``).
Call **after SfM** so a COLMAP ``DepthProvider`` can exist; the plan places
the stage after ``export`` by default. Do **not** import ingest / sfm /
train / export from this package — pass documented snapshots:

* **ingest** → ``list[FrameInput]`` (``frame_id``, ``width``, ``height``,
  RGB ``image``). Blur/dedup already applied.
* **sfm** → a ``DepthProvider`` implementation that samples ``Z`` + ``f_y``
  per ``frame_id`` (COLMAP ``cameras.bin`` / depth maps). Heuristic fallback
  is optional and will be marked low-confidence.
* **job payload** → ``user_height_meters`` persisted at upload time.

When
----
Once per job, idempotently. Re-running with the same frames and height must
produce the same ``CalibrationResult`` (pure function of its inputs besides
the optional live pose backend).

How the result enters the scene JSON
------------------------------------
Persist the camelCase fragment under ``scene.calibration``:

    scene_json["calibration"] = result.to_scene_dict()

The viewer (Fase 4) reads ``scaleFactor`` / ``source`` / ``confidence``:

* ``source == "auto-height"`` and confidence high → pre-apply on the scene
  root and ask *"a distância entre estes pontos parece X m?"*;
* confidence low or ``warnings`` non-empty → skip pre-apply and open the
  tape-measure guided flow. Manual confirmation overwrites ``source`` with
  ``"manual"`` using the same schema.

This function **never raises** because a person was missing, the pose
backend is absent, or depth is missing. Those paths return
``confidence = 0``, ``scaleFactor = 1`` (identity, do not distort the
scene) and an actionable pt-BR warning. ``ValueError`` is reserved for
invalid caller input (non-positive height).
"""

from __future__ import annotations

from collections.abc import Sequence

from autocal.backends import default_pose_backend
from autocal.backends.base import PersonPose, PoseBackend
from autocal.confidence import confidence_inputs_from_estimate, score_confidence
from autocal.depth import DepthProvider
from autocal.height_estimator import HeightEstimate, PoseFrame, estimate_person_height
from autocal.messages import (
    FEW_FRAMES_THRESHOLD,
    HIGH_VARIANCE_CV,
    MULTI_PERSON_RATIO_THRESHOLD,
    TYPICAL_HEIGHT_M,
    WARN_BAD_POSTURE,
    WARN_FEW_FRAMES,
    WARN_HEIGHT_RANGE,
    WARN_HEURISTIC_DEPTH,
    WARN_HIGH_VARIANCE,
    WARN_LOW_VISIBILITY,
    WARN_MULTI_PERSON,
    WARN_NO_BACKEND,
    WARN_NO_DEPTH,
    WARN_NO_FRAMES,
    WARN_NO_PERSON,
    WARN_NO_SCALE,
    WARN_PARTIAL_BODY,
)
from autocal.models import CalibrationResult
from autocal.scale_factor import aggregate_scale_factors
from autocal.stats import coefficient_of_variation
from autocal.types import FrameInput

# Mean critical visibility below which we warn about occlusion.
LOW_VISIBILITY_THRESHOLD: float = 0.55
# Full-body ratio below which we warn about partial crops.
PARTIAL_BODY_RATIO_THRESHOLD: float = 0.6
# Fraction of person-frames with bad posture that triggers a warning.
BAD_POSTURE_RATIO_THRESHOLD: float = 0.5


def run_auto_calibration(
    frames: Sequence[FrameInput],
    user_height_meters: float,
    *,
    backend: PoseBackend | None = None,
    depth_provider: DepthProvider | None = None,
) -> CalibrationResult:
    """Estimate a candidate scale factor from user height and posed frames.

    Parameters
    ----------
    frames:
        Extracted views (ingest). Precomputed ``poses`` short-circuit the
        backend — that is how tests stay free of mediapipe/mmpose.
    user_height_meters:
        Stature typed by the user at upload, **in metres**.
    backend:
        Optional ``PoseBackend``. When omitted, MediaPipe is tried, then
        MMPose; if neither extra is installed and frames have no poses,
        the result is a low-confidence identity with ``WARN_NO_BACKEND``.
    depth_provider:
        Pixel→scene conversion. ``None`` yields no scale (confidence 0).
    """
    if user_height_meters <= 0.0:
        raise ValueError("user_height_meters must be > 0 (metres)")

    warnings: list[str] = []
    lo_h, hi_h = TYPICAL_HEIGHT_M
    if not lo_h <= user_height_meters <= hi_h:
        warnings.append(WARN_HEIGHT_RANGE)

    if not frames:
        warnings.append(WARN_NO_FRAMES)
        return CalibrationResult.failed_auto(warnings)

    resolved_backend = backend
    needs_inference = any(frame.poses is None for frame in frames)
    if needs_inference and resolved_backend is None:
        resolved_backend = default_pose_backend()
        if resolved_backend is None:
            warnings.append(WARN_NO_BACKEND)

    pose_frames = [_resolve_pose_frame(frame, resolved_backend) for frame in frames]
    estimate = estimate_person_height(pose_frames, depth_provider=depth_provider)
    warnings.extend(_warnings_from_estimate(estimate, depth_provider))

    if estimate.estimated_height_scene_units is None or estimate.n_valid == 0:
        if WARN_NO_SCALE not in warnings:
            warnings.append(WARN_NO_SCALE)
        return CalibrationResult.failed_auto(warnings, frames_used=0)

    aggregation = aggregate_scale_factors(
        user_height_meters,
        estimate.inlier_scene_heights,
        estimate.inlier_weights,
    )
    confidence = score_confidence(confidence_inputs_from_estimate(estimate))
    return CalibrationResult(
        scale_factor=aggregation.scale_factor,
        source="auto-height",
        confidence=confidence,
        frames_used=aggregation.n_samples,
        estimated_person_height_scene_units=estimate.estimated_height_scene_units,
        error_estimate=aggregation.error_estimate,
        warnings=warnings,
    )


def _resolve_pose_frame(frame: FrameInput, backend: PoseBackend | None) -> PoseFrame:
    if frame.poses is not None:
        poses: list[PersonPose] = list(frame.poses)
    elif backend is not None and frame.image is not None:
        poses = backend.detect_persons(frame)
    else:
        poses = []
    return PoseFrame(
        frame_id=frame.frame_id,
        width=frame.width,
        height=frame.height,
        poses=poses,
    )


def _warnings_from_estimate(
    estimate: HeightEstimate,
    depth_provider: DepthProvider | None,
) -> list[str]:
    warnings: list[str] = []
    observations = estimate.observations
    with_person = [obs for obs in observations if obs.n_persons > 0]

    if not with_person:
        warnings.append(WARN_NO_PERSON)
        return warnings

    if depth_provider is None:
        warnings.append(WARN_NO_DEPTH)
    elif depth_provider.is_heuristic or estimate.used_heuristic_depth:
        warnings.append(WARN_HEURISTIC_DEPTH)

    full_body_ratio = estimate.n_full_body / max(len(with_person), 1)
    if full_body_ratio < PARTIAL_BODY_RATIO_THRESHOLD:
        warnings.append(WARN_PARTIAL_BODY)

    bad_posture_ratio = sum(1 for obs in with_person if not obs.posture_ok) / len(with_person)
    if bad_posture_ratio >= BAD_POSTURE_RATIO_THRESHOLD:
        warnings.append(WARN_BAD_POSTURE)

    if estimate.n_valid < FEW_FRAMES_THRESHOLD:
        warnings.append(WARN_FEW_FRAMES)

    if estimate.multi_person_ratio >= MULTI_PERSON_RATIO_THRESHOLD:
        warnings.append(WARN_MULTI_PERSON)

    if with_person:
        mean_vis = sum(obs.mean_visibility for obs in with_person) / len(with_person)
        if mean_vis < LOW_VISIBILITY_THRESHOLD:
            warnings.append(WARN_LOW_VISIBILITY)

    if len(estimate.inlier_scene_heights) >= 2:
        cv = coefficient_of_variation(estimate.inlier_scene_heights)
        if cv >= HIGH_VARIANCE_CV:
            warnings.append(WARN_HIGH_VARIANCE)

    return warnings
