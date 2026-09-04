"""MediaPipe Tasks Pose Landmarker backend.

Maps BlazePose's 33 landmarks onto the canonical names in ``backends.base``.
The native library is imported only via ``backends.mediapipe._deps``.
"""

from __future__ import annotations

from typing import Any, Final

from autocal.backends.base import (
    BackendUnavailableError,
    FrameLike,
    Keypoint,
    PersonPose,
    PoseBackend,
    bbox_from_keypoints,
    coerce_frame_image,
)
from autocal.backends.mediapipe._deps import (
    AVAILABLE,
    BaseOptions,
    PoseLandmarker,
    PoseLandmarkerOptions,
    RunningMode,
    mp,
)

# BlazePose / MediaPipe Pose landmark indices → canonical names.
# Inner/outer eyes, mouth and finger tips are dropped; the estimator only
# needs head / torso / feet.
_MEDIAPIPE_INDEX_TO_NAME: Final[dict[int, str]] = {
    0: "nose",
    2: "left_eye",
    5: "right_eye",
    7: "left_ear",
    8: "right_ear",
    11: "left_shoulder",
    12: "right_shoulder",
    13: "left_elbow",
    14: "right_elbow",
    15: "left_wrist",
    16: "right_wrist",
    23: "left_hip",
    24: "right_hip",
    25: "left_knee",
    26: "right_knee",
    27: "left_ankle",
    28: "right_ankle",
    29: "left_heel",
    30: "right_heel",
    31: "left_foot_index",
    32: "right_foot_index",
}


class MediaPipePoseBackend(PoseBackend):
    """Wrap ``PoseLandmarker`` (IMAGE mode) as a ``PoseBackend``.

    Parameters
    ----------
    model_asset_path:
        Path to ``pose_landmarker.task``. Required when the library is
        installed; the file is *not* downloaded by this package.
    num_poses:
        Upper bound on people per frame (multiple people lower confidence
        downstream).
    """

    def __init__(
        self,
        model_asset_path: str | None = None,
        *,
        num_poses: int = 3,
        min_pose_detection_confidence: float = 0.5,
        min_pose_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        if not AVAILABLE:
            raise BackendUnavailableError(
                "MediaPipe is not installed. See pipeline/autocal/requirements-autocal.txt "
                "(extra 'mediapipe')."
            )
        self._model_asset_path = model_asset_path
        self._num_poses = num_poses
        self._min_pose_detection_confidence = min_pose_detection_confidence
        self._min_pose_presence_confidence = min_pose_presence_confidence
        self._min_tracking_confidence = min_tracking_confidence
        self._landmarker: Any = None

    @classmethod
    def is_available(cls) -> bool:
        return bool(AVAILABLE)

    def detect_persons(self, frame: FrameLike) -> list[PersonPose]:
        image = coerce_frame_image(frame)
        landmarker = self._ensure_landmarker()
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        result = landmarker.detect(mp_image)
        people: list[PersonPose] = []
        for landmarks in result.pose_landmarks or []:
            person = _person_from_mediapipe(landmarks)
            if person is not None:
                people.append(person)
        return people

    def close(self) -> None:
        if self._landmarker is not None:
            closer = getattr(self._landmarker, "close", None)
            if closer is not None:
                closer()
            self._landmarker = None

    def _ensure_landmarker(self) -> Any:
        if self._landmarker is not None:
            return self._landmarker
        if not self._model_asset_path:
            raise BackendUnavailableError(
                "MediaPipe pose model path is required (pose_landmarker.task). "
                "Pass model_asset_path to MediaPipePoseBackend."
            )
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=self._model_asset_path),
            running_mode=RunningMode.IMAGE,
            num_poses=self._num_poses,
            min_pose_detection_confidence=self._min_pose_detection_confidence,
            min_pose_presence_confidence=self._min_pose_presence_confidence,
            min_tracking_confidence=self._min_tracking_confidence,
            output_segmentation_masks=False,
        )
        self._landmarker = PoseLandmarker.create_from_options(options)
        return self._landmarker


def _person_from_mediapipe(landmarks: Any) -> PersonPose | None:
    keypoints: dict[str, Keypoint] = {}
    for index, landmark in enumerate(landmarks):
        name = _MEDIAPIPE_INDEX_TO_NAME.get(index)
        if name is None:
            continue
        visibility = float(getattr(landmark, "visibility", 1.0) or 0.0)
        keypoints[name] = Keypoint(
            name=name,
            x=float(landmark.x),
            y=float(landmark.y),
            visibility=max(0.0, min(1.0, visibility)),
        )
    if not keypoints:
        return None
    visibilities = [kp.visibility for kp in keypoints.values()]
    score = sum(visibilities) / len(visibilities)
    return PersonPose(
        keypoints=keypoints,
        bbox=bbox_from_keypoints(keypoints),
        detection_score=score,
    )
