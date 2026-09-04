"""MMPose / RTMPose backend.

Uses ``MMPoseInferencer`` (top-down RTMPose + a person detector) and maps the
COCO-17 skeleton onto the canonical names in ``backends.base``. The native
library is imported only via ``backends.mmpose._deps``.
"""

from __future__ import annotations

from typing import Any, Final

from autocal.backends.base import (
    BackendUnavailableError,
    BoundingBox,
    FrameLike,
    Keypoint,
    PersonPose,
    PoseBackend,
    bbox_from_keypoints,
    coerce_frame_image,
)
from autocal.backends.mmpose._deps import AVAILABLE, MMPoseInferencer

# COCO-17 keypoint order used by RTMPose / MMPose human2d models.
_COCO17_INDEX_TO_NAME: Final[dict[int, str]] = {
    0: "nose",
    1: "left_eye",
    2: "right_eye",
    3: "left_ear",
    4: "right_ear",
    5: "left_shoulder",
    6: "right_shoulder",
    7: "left_elbow",
    8: "right_elbow",
    9: "left_wrist",
    10: "right_wrist",
    11: "left_hip",
    12: "right_hip",
    13: "left_knee",
    14: "right_knee",
    15: "left_ankle",
    16: "right_ankle",
}


class MMPoseBackend(PoseBackend):
    """Wrap ``MMPoseInferencer`` as a ``PoseBackend``.

    Parameters
    ----------
    pose2d:
        MMPose inferencer alias (default ``human`` → RTMPose + detector).
        The Fase 1 benchmark should try ``rtmpose-m`` / ``rtmpose-l`` here.
    device:
        ``cpu`` or ``cuda:0``. ``None`` lets MMPose pick.
    """

    def __init__(
        self,
        pose2d: str = "human",
        *,
        device: str | None = None,
        inferencer: Any | None = None,
    ) -> None:
        if inferencer is None and not AVAILABLE:
            raise BackendUnavailableError(
                "MMPose is not installed. See pipeline/autocal/requirements-autocal.txt "
                "(extra 'mmpose')."
            )
        self._pose2d = pose2d
        self._device = device
        self._inferencer = inferencer

    @classmethod
    def is_available(cls) -> bool:
        return bool(AVAILABLE)

    def detect_persons(self, frame: FrameLike) -> list[PersonPose]:
        image = coerce_frame_image(frame)
        inferencer = self._ensure_inferencer()
        height, width = _image_hw(image)
        people: list[PersonPose] = []
        for payload in inferencer(image, return_vis=False):
            people.extend(_people_from_mmpose_payload(payload, width=width, height=height))
        return people

    def close(self) -> None:
        self._inferencer = None

    def _ensure_inferencer(self) -> Any:
        if self._inferencer is not None:
            return self._inferencer
        kwargs: dict[str, Any] = {"pose2d": self._pose2d}
        if self._device is not None:
            kwargs["device"] = self._device
        self._inferencer = MMPoseInferencer(**kwargs)
        return self._inferencer


def _image_hw(image: Any) -> tuple[int, int]:
    shape = getattr(image, "shape", None)
    if shape is None or len(shape) < 2:
        raise TypeError("MMPose backend expects an image with a .shape of (H, W, …)")
    return int(shape[0]), int(shape[1])


def _people_from_mmpose_payload(
    payload: dict[str, Any],
    *,
    width: int,
    height: int,
) -> list[PersonPose]:
    raw_predictions = payload.get("predictions", [])
    if not raw_predictions:
        return []
    first = raw_predictions[0]
    instances: list[Any]
    if first and isinstance(first, dict) and "keypoints" in first:
        instances = raw_predictions  # already a list of instances
    elif first and isinstance(first, list):
        instances = first
    else:
        instances = []

    people: list[PersonPose] = []
    for instance in instances:
        person = _person_from_coco17(instance, width=width, height=height)
        if person is not None:
            people.append(person)
    return people


def _person_from_coco17(instance: dict[str, Any], *, width: int, height: int) -> PersonPose | None:
    keypoints_xy = instance.get("keypoints") or []
    scores = instance.get("keypoint_scores") or instance.get("keypoint_score") or []
    if not keypoints_xy:
        return None
    keypoints: dict[str, Keypoint] = {}
    for index, xy in enumerate(keypoints_xy):
        name = _COCO17_INDEX_TO_NAME.get(index)
        if name is None or len(xy) < 2:
            continue
        score = float(scores[index]) if index < len(scores) else 1.0
        # MMPose emits pixel coordinates; normalize to [0, 1].
        keypoints[name] = Keypoint(
            name=name,
            x=float(xy[0]) / max(width, 1),
            y=float(xy[1]) / max(height, 1),
            visibility=max(0.0, min(1.0, score)),
        )
    if not keypoints:
        return None

    bbox = _bbox_from_instance(instance, width=width, height=height)
    if bbox is None:
        bbox = bbox_from_keypoints(keypoints)
    visibilities = [kp.visibility for kp in keypoints.values()]
    return PersonPose(
        keypoints=keypoints,
        bbox=bbox,
        detection_score=sum(visibilities) / len(visibilities),
    )


def _bbox_from_instance(instance: dict[str, Any], *, width: int, height: int) -> BoundingBox | None:
    raw = instance.get("bbox")
    if raw is None:
        return None
    # Common layouts: [x1, y1, x2, y2] or [[x1, y1, x2, y2]] or [x, y, w, h].
    box = raw[0] if raw and isinstance(raw[0], (list, tuple)) else raw
    if len(box) < 4:
        return None
    x1, y1, a, b = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
    # Heuristic: if a,b look like a bottom-right corner, treat as x2,y2.
    if a > x1 and b > y1 and a <= width * 1.05 and b <= height * 1.05:
        x2, y2 = a, b
    else:
        x2, y2 = x1 + a, y1 + b
    return BoundingBox(
        x_min=x1 / max(width, 1),
        y_min=y1 / max(height, 1),
        x_max=x2 / max(width, 1),
        y_max=y2 / max(height, 1),
    )
