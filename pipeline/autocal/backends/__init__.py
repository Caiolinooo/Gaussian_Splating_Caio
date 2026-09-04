"""Pose backends for auto-calibration (MediaPipe Tasks and MMPose/RTMPose)."""

from __future__ import annotations

from typing import Any, Never

from autocal.backends.base import (
    CRITICAL_KEYPOINT_NAMES,
    FOOT_KEYPOINT_NAMES,
    HEAD_KEYPOINT_NAMES,
    BackendUnavailableError,
    BoundingBox,
    Keypoint,
    PersonPose,
    PoseBackend,
    PoseBackendName,
)
from autocal.backends.mediapipe_backend import MediaPipePoseBackend
from autocal.backends.mmpose_backend import MMPoseBackend

__all__ = [
    "CRITICAL_KEYPOINT_NAMES",
    "FOOT_KEYPOINT_NAMES",
    "HEAD_KEYPOINT_NAMES",
    "BackendUnavailableError",
    "BoundingBox",
    "Keypoint",
    "MMPoseBackend",
    "MediaPipePoseBackend",
    "PersonPose",
    "PoseBackend",
    "PoseBackendName",
    "create_pose_backend",
    "default_pose_backend",
]


def _unhandled_backend(name: Never) -> Never:
    raise RuntimeError(f"unhandled PoseBackendName: {name}")


def create_pose_backend(name: PoseBackendName, **kwargs: Any) -> PoseBackend:
    """Construct a backend by name.

    Instantiating a backend whose optional library is missing raises
    ``BackendUnavailableError``. The ``match`` is exhaustive over
    ``PoseBackendName`` so a new variant fails at type-check time.
    """
    match name:
        case PoseBackendName.MEDIAPIPE:
            return MediaPipePoseBackend(**kwargs)
        case PoseBackendName.MMPOSE:
            return MMPoseBackend(**kwargs)
        case _:
            return _unhandled_backend(name)


def default_pose_backend() -> PoseBackend | None:
    """Prefer MediaPipe (lighter) then MMPose. ``None`` if neither extra is installed."""
    if MediaPipePoseBackend.is_available():
        return MediaPipePoseBackend()
    if MMPoseBackend.is_available():
        return MMPoseBackend()
    return None
