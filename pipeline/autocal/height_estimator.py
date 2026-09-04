"""Estimate a person's height in reconstruction units from 2D poses.

Mathematics
===========

1. **Pixel stature (per frame)**

   Image origin is top-left, ``y`` increases downward, keypoints are
   normalized to ``[0, 1]``.

   *Crown.* Take the highest visible head landmark (smallest ``y`` among
   nose / eyes / ears). The true vertex sits *above* the tragion (ears).
   Using adult anthropometry (head height ≈ 13 % of stature; biauricular
   breadth ≈ 0.8 × head height):

       Δy_crown ≈ 0.55 × |x_left_ear − x_right_ear|     (preferred)
                ≈ 0.22 × shoulder_breadth                 (fallback)

   so ``y_crown = y_top_head − Δy_crown``.

   *Feet.* Take the lowest visible foot landmark (largest ``y`` among
   ankles / heels / toes). Heels and toe tips already reach the ground. If
   only the malleoli are visible, add

       Δy_ankle ≈ 0.10 × shoulder_breadth

   *Pixel height.* ``h_px = (y_feet − y_crown) × image_height``.

2. **Full-body gate**

   A frame is usable only when a head landmark, **both** feet (left and
   right), and a torso pair (shoulders or hips) exceed the visibility
   threshold. Partial crops bias stature short and are dropped.

3. **Posture gate**

   Crouching or leaning shortens the vertical span. We require:

   * torso verticality ``|Δy| / ||shoulder→hip|| ≥ 0.85``;
   * leg extension ``||hip−ankle|| / (||hip−knee|| + ||knee−ankle||) ≥ 0.90``
     (1.0 = straight). Combined score must be ``≥ 0.82``.

4. **Pixels → scene units**

   Via ``DepthProvider`` (pinhole): ``H_scene = h_px × Z / f_y``.
   See ``depth.py`` for the derivation. Frames without a depth sample are
   kept for diagnostics but do not vote on the metric height.

5. **Outliers**

   Inlier scene heights are those inside Tukey fences
   ``[Q1 − 1.5 IQR, Q3 + 1.5 IQR]``. The reported height is the
   **visibility-weighted median** of inliers.

The primary person in a multi-person frame is the largest, most complete
bbox (see ``select_primary_person``). Multiple people still penalise the
confidence score.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from autocal.backends.base import (
    CRITICAL_KEYPOINT_NAMES,
    FOOT_KEYPOINT_NAMES,
    HEAD_KEYPOINT_NAMES,
    LEFT_FOOT_KEYPOINT_NAMES,
    RIGHT_FOOT_KEYPOINT_NAMES,
    Keypoint,
    PersonPose,
)
from autocal.depth import DepthProvider
from autocal.stats import iqr_inlier_mask, weighted_median

# Visibility required to use a landmark in geometry.
VISIBILITY_THRESHOLD: float = 0.5

# Anthropometric crown / ground offsets (see module docstring).
CROWN_OFFSET_FROM_INTER_EAR: float = 0.55
CROWN_OFFSET_FROM_SHOULDER_WIDTH: float = 0.22
ANKLE_TO_GROUND_FROM_SHOULDER: float = 0.10
# Weak fallback when neither ears nor shoulders are visible (~3.5 % of frame).
CROWN_OFFSET_FALLBACK_NORM: float = 0.035

# Posture / full-body gates.
TORSO_VERTICALITY_MIN: float = 0.85
LEG_EXTENSION_MIN: float = 0.90
POSTURE_SCORE_MIN: float = 0.82

GROUND_FOOT_NAMES: tuple[str, ...] = (
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
)


@dataclass(frozen=True, slots=True)
class PixelStature:
    """Geometric measurement of one person in one frame (pixels + gates)."""

    pixel_height: float
    crown_xy: tuple[float, float]
    feet_xy: tuple[float, float]
    full_body_visible: bool
    posture_score: float
    mean_visibility: float
    occlusion: float


@dataclass
class FrameObservation:
    """Per-frame diagnostics consumed by confidence scoring."""

    frame_id: str
    n_persons: int
    full_body_visible: bool
    posture_ok: bool
    mean_visibility: float
    occlusion: float
    pixel_height: float | None
    scene_height: float | None
    frame_weight: float
    reject_reason: str | None = None
    crown_xy: tuple[float, float] | None = None
    feet_xy: tuple[float, float] | None = None


@dataclass
class HeightEstimate:
    """Aggregated person height in scene units plus the raw observations."""

    observations: list[FrameObservation] = field(default_factory=list)
    estimated_height_scene_units: float | None = None
    inlier_scene_heights: list[float] = field(default_factory=list)
    inlier_weights: list[float] = field(default_factory=list)
    used_heuristic_depth: bool = False

    @property
    def n_valid(self) -> int:
        return len(self.inlier_scene_heights)

    @property
    def n_with_person(self) -> int:
        return sum(1 for obs in self.observations if obs.n_persons > 0)

    @property
    def n_full_body(self) -> int:
        return sum(1 for obs in self.observations if obs.full_body_visible)

    @property
    def multi_person_ratio(self) -> float:
        if not self.observations:
            return 0.0
        return sum(1 for obs in self.observations if obs.n_persons > 1) / len(self.observations)


def visible_keypoint(
    keypoints: Mapping[str, Keypoint],
    name: str,
    *,
    threshold: float = VISIBILITY_THRESHOLD,
) -> Keypoint | None:
    keypoint = keypoints.get(name)
    if keypoint is None or keypoint.visibility < threshold:
        return None
    return keypoint


def mean_critical_visibility(keypoints: Mapping[str, Keypoint]) -> float:
    scores = [
        keypoints[name].visibility if name in keypoints else 0.0 for name in CRITICAL_KEYPOINT_NAMES
    ]
    return sum(scores) / len(scores)


def is_full_body_visible(
    keypoints: Mapping[str, Keypoint],
    *,
    threshold: float = VISIBILITY_THRESHOLD,
) -> bool:
    has_head = any(visible_keypoint(keypoints, name, threshold=threshold) for name in HEAD_KEYPOINT_NAMES)
    has_left_foot = any(
        visible_keypoint(keypoints, name, threshold=threshold) for name in LEFT_FOOT_KEYPOINT_NAMES
    )
    has_right_foot = any(
        visible_keypoint(keypoints, name, threshold=threshold) for name in RIGHT_FOOT_KEYPOINT_NAMES
    )
    has_shoulders = (
        visible_keypoint(keypoints, "left_shoulder", threshold=threshold) is not None
        and visible_keypoint(keypoints, "right_shoulder", threshold=threshold) is not None
    )
    has_hips = (
        visible_keypoint(keypoints, "left_hip", threshold=threshold) is not None
        and visible_keypoint(keypoints, "right_hip", threshold=threshold) is not None
    )
    return bool(has_head and has_left_foot and has_right_foot and (has_shoulders or has_hips))


def _midpoint(a: Keypoint, b: Keypoint) -> tuple[float, float]:
    return ((a.x + b.x) * 0.5, (a.y + b.y) * 0.5)


def _dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def posture_score(keypoints: Mapping[str, Keypoint]) -> float:
    """1.0 ≈ standing upright; lower values mean lean / crouch / sit.

    Combines torso verticality and left/right leg extension (see module math).
    Returns 0.5 when too few landmarks exist to judge (unknown, not fatal).
    """
    scores: list[float] = []
    left_shoulder = visible_keypoint(keypoints, "left_shoulder")
    right_shoulder = visible_keypoint(keypoints, "right_shoulder")
    left_hip = visible_keypoint(keypoints, "left_hip")
    right_hip = visible_keypoint(keypoints, "right_hip")

    if left_shoulder and right_shoulder and left_hip and right_hip:
        shx, shy = _midpoint(left_shoulder, right_shoulder)
        hx, hy = _midpoint(left_hip, right_hip)
        length = _dist(shx, shy, hx, hy)
        if length > 1e-6:
            scores.append(abs(hy - shy) / length)

    sides = (
        (left_hip, visible_keypoint(keypoints, "left_knee"), visible_keypoint(keypoints, "left_ankle")),
        (right_hip, visible_keypoint(keypoints, "right_knee"), visible_keypoint(keypoints, "right_ankle")),
    )
    for hip, knee, ankle in sides:
        if hip is None or knee is None or ankle is None:
            continue
        thigh = _dist(hip.x, hip.y, knee.x, knee.y)
        shin = _dist(knee.x, knee.y, ankle.x, ankle.y)
        chord = _dist(hip.x, hip.y, ankle.x, ankle.y)
        chain = thigh + shin
        if chain > 1e-6:
            scores.append(chord / chain)

    if not scores:
        return 0.5
    return sum(scores) / len(scores)


def select_primary_person(poses: Sequence[PersonPose]) -> PersonPose:
    """Pick the most likely 'user': largest bbox, then more complete skeleton."""

    def score(person: PersonPose) -> float:
        complete = sum(1 for kp in person.keypoints.values() if kp.visibility >= VISIBILITY_THRESHOLD)
        return person.bbox.area * (1.0 + 0.05 * complete) * max(person.detection_score, 0.1)

    return max(poses, key=score)


def measure_pixel_stature(
    pose: PersonPose,
    image_width: int,
    image_height: int,
    *,
    visibility_threshold: float = VISIBILITY_THRESHOLD,
) -> PixelStature | None:
    """Crown→feet pixel height plus visibility / posture diagnostics.

    Returns ``None`` only when head or feet landmarks are missing entirely
    (cannot form a vertical span). Partial-body and bad-posture cases still
    return a ``PixelStature`` so callers can record why the frame was gated.
    """
    if image_width <= 0 or image_height <= 0:
        return None
    keypoints = pose.keypoints
    head_pts = [
        kp
        for name in HEAD_KEYPOINT_NAMES
        if (kp := visible_keypoint(keypoints, name, threshold=visibility_threshold)) is not None
    ]
    foot_pts = [
        kp
        for name in FOOT_KEYPOINT_NAMES
        if (kp := visible_keypoint(keypoints, name, threshold=visibility_threshold)) is not None
    ]
    if not head_pts or not foot_pts:
        return None

    top = min(head_pts, key=lambda kp: kp.y)
    bottom = max(foot_pts, key=lambda kp: kp.y)

    left_ear = visible_keypoint(keypoints, "left_ear", threshold=visibility_threshold)
    right_ear = visible_keypoint(keypoints, "right_ear", threshold=visibility_threshold)
    left_shoulder = visible_keypoint(keypoints, "left_shoulder", threshold=visibility_threshold)
    right_shoulder = visible_keypoint(keypoints, "right_shoulder", threshold=visibility_threshold)

    if left_ear is not None and right_ear is not None:
        inter_ear_px = abs(left_ear.x - right_ear.x) * float(image_width)
        crown_offset_px = CROWN_OFFSET_FROM_INTER_EAR * inter_ear_px
    elif left_shoulder is not None and right_shoulder is not None:
        shoulder_px = abs(left_shoulder.x - right_shoulder.x) * float(image_width)
        crown_offset_px = CROWN_OFFSET_FROM_SHOULDER_WIDTH * shoulder_px
    else:
        crown_offset_px = CROWN_OFFSET_FALLBACK_NORM * float(image_height)

    y_crown = top.y - crown_offset_px / float(image_height)
    x_crown = top.x

    has_ground = any(
        visible_keypoint(keypoints, name, threshold=visibility_threshold) is not None
        for name in GROUND_FOOT_NAMES
    )
    y_feet = bottom.y
    if not has_ground and left_shoulder is not None and right_shoulder is not None:
        shoulder_px = abs(left_shoulder.x - right_shoulder.x) * float(image_width)
        y_feet = bottom.y + (ANKLE_TO_GROUND_FROM_SHOULDER * shoulder_px) / float(image_height)

    height_norm = y_feet - y_crown
    if height_norm <= 1e-6:
        return None

    visibility = mean_critical_visibility(keypoints)
    return PixelStature(
        pixel_height=height_norm * float(image_height),
        crown_xy=(x_crown, y_crown),
        feet_xy=(bottom.x, y_feet),
        full_body_visible=is_full_body_visible(keypoints, threshold=visibility_threshold),
        posture_score=posture_score(keypoints),
        mean_visibility=visibility,
        occlusion=1.0 - visibility,
    )


def _observe_frame(
    frame_id: str,
    width: int,
    height: int,
    poses: Sequence[PersonPose],
    depth_provider: DepthProvider | None,
) -> FrameObservation:
    if not poses:
        return FrameObservation(
            frame_id=frame_id,
            n_persons=0,
            full_body_visible=False,
            posture_ok=False,
            mean_visibility=0.0,
            occlusion=1.0,
            pixel_height=None,
            scene_height=None,
            frame_weight=0.0,
            reject_reason="no_person",
        )

    primary = select_primary_person(poses)
    stature = measure_pixel_stature(primary, width, height)
    if stature is None:
        visibility = mean_critical_visibility(primary.keypoints)
        return FrameObservation(
            frame_id=frame_id,
            n_persons=len(poses),
            full_body_visible=False,
            posture_ok=False,
            mean_visibility=visibility,
            occlusion=1.0 - visibility,
            pixel_height=None,
            scene_height=None,
            frame_weight=0.0,
            reject_reason="incomplete_skeleton",
        )

    posture_ok = stature.posture_score >= POSTURE_SCORE_MIN
    if not stature.full_body_visible:
        reason: str | None = "partial_body"
        weight = 0.0
    elif not posture_ok:
        reason = "bad_posture"
        weight = 0.0
    else:
        reason = None
        weight = max(stature.mean_visibility, 1e-3) * stature.posture_score

    scene_height: float | None = None
    if weight > 0.0 and depth_provider is not None:
        scene_height = depth_provider.person_height_scene_units(
            frame_id,
            stature.crown_xy,
            stature.feet_xy,
            (width, height),
        )
        if scene_height is None or scene_height <= 1e-9:
            reason = "no_depth"
            weight = 0.0
            scene_height = None

    return FrameObservation(
        frame_id=frame_id,
        n_persons=len(poses),
        full_body_visible=stature.full_body_visible,
        posture_ok=posture_ok,
        mean_visibility=stature.mean_visibility,
        occlusion=stature.occlusion,
        pixel_height=stature.pixel_height,
        scene_height=scene_height,
        frame_weight=weight,
        reject_reason=reason,
        crown_xy=stature.crown_xy,
        feet_xy=stature.feet_xy,
    )


@dataclass(frozen=True, slots=True)
class PoseFrame:
    """Frame already resolved to detections (service does pose inference)."""

    frame_id: str
    width: int
    height: int
    poses: list[PersonPose]


def estimate_person_height(
    frames: Sequence[PoseFrame],
    depth_provider: DepthProvider | None = None,
) -> HeightEstimate:
    """Run per-frame gates, convert to scene units, drop IQR outliers."""
    observations = [
        _observe_frame(frame.frame_id, frame.width, frame.height, frame.poses, depth_provider)
        for frame in frames
    ]

    candidates = [
        (obs.scene_height, obs.frame_weight)
        for obs in observations
        if obs.scene_height is not None and obs.frame_weight > 0.0
    ]
    if not candidates:
        return HeightEstimate(
            observations=observations,
            used_heuristic_depth=bool(depth_provider is not None and depth_provider.is_heuristic),
        )

    heights = [height for height, _weight in candidates]
    weights = [weight for _height, weight in candidates]
    mask = iqr_inlier_mask(heights)
    inlier_heights = [height for height, keep in zip(heights, mask, strict=True) if keep]
    inlier_weights = [weight for weight, keep in zip(weights, mask, strict=True) if keep]
    if not inlier_heights:
        inlier_heights = heights
        inlier_weights = weights

    estimated = weighted_median(inlier_heights, inlier_weights)
    return HeightEstimate(
        observations=observations,
        estimated_height_scene_units=estimated,
        inlier_scene_heights=inlier_heights,
        inlier_weights=inlier_weights,
        used_heuristic_depth=bool(depth_provider is not None and depth_provider.is_heuristic),
    )
