"""Pose backend contract shared by MediaPipe Tasks and MMPose/RTMPose.

The Fase 1 benchmark (tasks.md §7, open decision) will pick a default. Until
then both implementations sit behind ``PoseBackend``. Downstream code
(``height_estimator``, ``service``) must never import a concrete backend
except through ``create_pose_backend`` / ``default_pose_backend``.

Coordinate convention
---------------------
Keypoints are **normalized to [0, 1]** in image space, origin at the
**top-left**, ``y`` growing downward (OpenCV / MediaPipe / COCO). Visibility
is a per-keypoint score in ``[0, 1]`` (1 = clearly seen).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, Protocol, runtime_checkable

# Canonical names consumed by the height estimator. Both backends map their
# native skeletons onto this set (MediaPipe 33 → subset; COCO-17 → subset).
HEAD_KEYPOINT_NAMES: Final[tuple[str, ...]] = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
)
LEFT_FOOT_KEYPOINT_NAMES: Final[tuple[str, ...]] = (
    "left_ankle",
    "left_heel",
    "left_foot_index",
)
RIGHT_FOOT_KEYPOINT_NAMES: Final[tuple[str, ...]] = (
    "right_ankle",
    "right_heel",
    "right_foot_index",
)
FOOT_KEYPOINT_NAMES: Final[tuple[str, ...]] = LEFT_FOOT_KEYPOINT_NAMES + RIGHT_FOOT_KEYPOINT_NAMES
TORSO_KEYPOINT_NAMES: Final[tuple[str, ...]] = (
    "left_shoulder",
    "right_shoulder",
    "left_hip",
    "right_hip",
)
CRITICAL_KEYPOINT_NAMES: Final[tuple[str, ...]] = (
    "nose",
    "left_shoulder",
    "right_shoulder",
    "left_hip",
    "right_hip",
    "left_ankle",
    "right_ankle",
)


class PoseBackendName(StrEnum):
    """Registered pose backends. Exhaustive ``match`` lives in the factory."""

    MEDIAPIPE = "mediapipe"
    MMPOSE = "mmpose"


class BackendUnavailableError(RuntimeError):
    """Raised when a requested backend's optional dependency is not installed."""


@dataclass(frozen=True, slots=True)
class Keypoint:
    """A single skeleton landmark in normalized image coordinates."""

    name: str
    x: float
    y: float
    visibility: float

    def is_visible(self, threshold: float = 0.5) -> bool:
        return self.visibility >= threshold


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Axis-aligned box in normalized image coordinates."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def area(self) -> float:
        return max(0.0, self.x_max - self.x_min) * max(0.0, self.y_max - self.y_min)

    @property
    def width(self) -> float:
        return max(0.0, self.x_max - self.x_min)

    @property
    def height(self) -> float:
        return max(0.0, self.y_max - self.y_min)


@dataclass(frozen=True, slots=True)
class PersonPose:
    """One detected person: canonical keypoints + bbox + detector score."""

    keypoints: dict[str, Keypoint]
    bbox: BoundingBox
    detection_score: float = 1.0


@runtime_checkable
class HasImage(Protocol):
    """Minimal frame protocol. ``image`` is RGB ``uint8`` with shape ``(H, W, 3)``."""

    image: Any


#: RGB array-like ``(H, W, 3)`` or an object exposing ``.image``.
FrameLike = Any


def coerce_frame_image(frame: FrameLike) -> Any:
    """Extract the RGB image from a raw array or a ``HasImage`` object."""
    image = frame.image if isinstance(frame, HasImage) or hasattr(frame, "image") else frame
    if image is None:
        raise TypeError("frame image is None; pass an RGB array or a FrameInput with image set")
    return image


def bbox_from_keypoints(keypoints: dict[str, Keypoint], *, min_visibility: float = 0.2) -> BoundingBox:
    """Tight box around visible landmarks; unit box if none are visible."""
    xs: list[float] = []
    ys: list[float] = []
    for keypoint in keypoints.values():
        if keypoint.visibility >= min_visibility:
            xs.append(keypoint.x)
            ys.append(keypoint.y)
    if not xs:
        return BoundingBox(0.0, 0.0, 1.0, 1.0)
    return BoundingBox(min(xs), min(ys), max(xs), max(ys))


class PoseBackend(ABC):
    """Detect people and 2D poses on a single RGB frame.

    Implementations must:
    - return an empty list when nobody is found (never raise for that);
    - emit canonical keypoint names from this module;
    - keep imports of mediapipe / mmpose / torch inside their ``_deps`` module.
    """

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """True when the optional Python package imported successfully."""

    @abstractmethod
    def detect_persons(self, frame: FrameLike) -> list[PersonPose]:
        """Return every person detected in ``frame``.

        Parameters
        ----------
        frame:
            RGB ``uint8`` array ``(H, W, 3)`` or an object with an ``image``
            attribute of that shape (the ingest ``FrameInput``).
        """

    def close(self) -> None:
        """Release native resources. Default is a no-op."""
        return None
