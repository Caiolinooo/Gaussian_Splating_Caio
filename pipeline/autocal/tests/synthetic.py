"""Deterministic standing / partial / crouched skeletons for tests."""

from __future__ import annotations

from autocal.backends.base import Keypoint, PersonPose, bbox_from_keypoints
from autocal.types import FrameInput

IMAGE_WIDTH: int = 1920
IMAGE_HEIGHT: int = 1080


def _kp(name: str, x: float, y: float, visibility: float = 0.98) -> Keypoint:
    return Keypoint(name=name, x=x, y=y, visibility=visibility)


def standing_keypoints(
    *,
    center_x: float = 0.50,
    head_y: float = 0.16,
    feet_y: float = 0.90,
    shoulder_half_width: float = 0.08,
    visibility: float = 0.98,
    include_ground_contacts: bool = True,
    include_feet: bool = True,
    crouch: bool = False,
) -> dict[str, Keypoint]:
    """Build a canonical adult skeleton in normalized image coordinates."""
    cx = center_x
    shw = shoulder_half_width
    keypoints: dict[str, Keypoint] = {
        "nose": _kp("nose", cx, head_y + 0.02, visibility),
        "left_eye": _kp("left_eye", cx - 0.015, head_y + 0.01, visibility),
        "right_eye": _kp("right_eye", cx + 0.015, head_y + 0.01, visibility),
        "left_ear": _kp("left_ear", cx - 0.03, head_y, visibility),
        "right_ear": _kp("right_ear", cx + 0.03, head_y, visibility),
        "left_shoulder": _kp("left_shoulder", cx - shw, head_y + 0.12, visibility),
        "right_shoulder": _kp("right_shoulder", cx + shw, head_y + 0.12, visibility),
        "left_elbow": _kp("left_elbow", cx - shw - 0.03, head_y + 0.25, visibility),
        "right_elbow": _kp("right_elbow", cx + shw + 0.03, head_y + 0.25, visibility),
        "left_wrist": _kp("left_wrist", cx - shw - 0.02, head_y + 0.36, visibility),
        "right_wrist": _kp("right_wrist", cx + shw + 0.02, head_y + 0.36, visibility),
    }

    if crouch:
        keypoints["left_hip"] = _kp("left_hip", cx - shw * 0.7, 0.48, visibility)
        keypoints["right_hip"] = _kp("right_hip", cx + shw * 0.7, 0.48, visibility)
        keypoints["left_knee"] = _kp("left_knee", cx - shw * 0.6 + 0.18, 0.55, visibility)
        keypoints["right_knee"] = _kp("right_knee", cx + shw * 0.6 + 0.18, 0.55, visibility)
        keypoints["left_ankle"] = _kp("left_ankle", cx - shw * 0.5, 0.82, visibility)
        keypoints["right_ankle"] = _kp("right_ankle", cx + shw * 0.5, 0.82, visibility)
        if include_ground_contacts:
            keypoints["left_heel"] = _kp("left_heel", cx - shw * 0.5, 0.84, visibility)
            keypoints["right_heel"] = _kp("right_heel", cx + shw * 0.5, 0.84, visibility)
        return keypoints

    hip_y = head_y + 0.36
    knee_y = head_y + 0.55
    ankle_y = feet_y - 0.03
    keypoints["left_hip"] = _kp("left_hip", cx - shw * 0.7, hip_y, visibility)
    keypoints["right_hip"] = _kp("right_hip", cx + shw * 0.7, hip_y, visibility)
    keypoints["left_knee"] = _kp("left_knee", cx - shw * 0.6, knee_y, visibility)
    keypoints["right_knee"] = _kp("right_knee", cx + shw * 0.6, knee_y, visibility)

    if include_feet:
        keypoints["left_ankle"] = _kp("left_ankle", cx - shw * 0.5, ankle_y, visibility)
        keypoints["right_ankle"] = _kp("right_ankle", cx + shw * 0.5, ankle_y, visibility)
        if include_ground_contacts:
            keypoints["left_heel"] = _kp("left_heel", cx - shw * 0.5, feet_y, visibility)
            keypoints["right_heel"] = _kp("right_heel", cx + shw * 0.5, feet_y, visibility)
            keypoints["left_foot_index"] = _kp(
                "left_foot_index", cx - shw * 0.35, feet_y - 0.005, visibility
            )
            keypoints["right_foot_index"] = _kp(
                "right_foot_index", cx + shw * 0.35, feet_y - 0.005, visibility
            )
    return keypoints


def scale_keypoints_vertical(
    keypoints: dict[str, Keypoint],
    scale: float,
    *,
    pivot_y: float = 0.53,
) -> dict[str, Keypoint]:
    """Shrink/stretch a skeleton along Y while keeping joint angles (standing)."""
    scaled: dict[str, Keypoint] = {}
    for name, keypoint in keypoints.items():
        scaled[name] = Keypoint(
            name=keypoint.name,
            x=keypoint.x,
            y=pivot_y + (keypoint.y - pivot_y) * scale,
            visibility=keypoint.visibility,
        )
    return scaled


def make_person(
    keypoints: dict[str, Keypoint] | None = None,
    *,
    detection_score: float = 0.95,
    **standing_kwargs: object,
) -> PersonPose:
    kpts = keypoints if keypoints is not None else standing_keypoints(**standing_kwargs)  # type: ignore[arg-type]
    return PersonPose(
        keypoints=kpts,
        bbox=bbox_from_keypoints(kpts),
        detection_score=detection_score,
    )


def make_frame(
    frame_id: str,
    poses: list[PersonPose] | None,
    *,
    width: int = IMAGE_WIDTH,
    height: int = IMAGE_HEIGHT,
) -> FrameInput:
    return FrameInput(
        frame_id=frame_id,
        width=width,
        height=height,
        image=None,
        poses=poses,
    )


def standing_frames(count: int, *, prefix: str = "f") -> list[FrameInput]:
    person = make_person()
    return [make_frame(f"{prefix}{index:03d}", [person]) for index in range(count)]
