"""Backends import without mediapipe/mmpose; mapping works on synthetic payloads."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from autocal.backends import create_pose_backend, default_pose_backend
from autocal.backends.base import BackendUnavailableError, PoseBackendName
from autocal.backends.mediapipe._deps import AVAILABLE as MP_AVAILABLE
from autocal.backends.mediapipe_backend import MediaPipePoseBackend
from autocal.backends.mmpose._deps import AVAILABLE as MM_AVAILABLE
from autocal.backends.mmpose_backend import MMPoseBackend


def test_optional_deps_flags_are_booleans() -> None:
    assert MP_AVAILABLE in {True, False}
    assert MM_AVAILABLE in {True, False}


def test_constructing_mediapipe_without_lib_raises() -> None:
    if MediaPipePoseBackend.is_available():
        pytest.skip("mediapipe is installed in this environment")
    with pytest.raises(BackendUnavailableError, match="MediaPipe"):
        MediaPipePoseBackend()


def test_constructing_mmpose_without_lib_raises() -> None:
    if MMPoseBackend.is_available():
        pytest.skip("mmpose is installed in this environment")
    with pytest.raises(BackendUnavailableError, match="MMPose"):
        MMPoseBackend()


def test_factory_is_exhaustive_over_enum() -> None:
    for name in PoseBackendName:
        if name is PoseBackendName.MEDIAPIPE and not MediaPipePoseBackend.is_available():
            with pytest.raises(BackendUnavailableError):
                create_pose_backend(name)
        elif name is PoseBackendName.MMPOSE and not MMPoseBackend.is_available():
            with pytest.raises(BackendUnavailableError):
                create_pose_backend(name)
        else:
            backend = create_pose_backend(name)
            assert backend.is_available()


def test_default_backend_is_none_when_extras_missing() -> None:
    if MediaPipePoseBackend.is_available() or MMPoseBackend.is_available():
        pytest.skip("a pose extra is installed")
    assert default_pose_backend() is None


def test_mmpose_maps_coco17_pixels_to_normalized_keypoints() -> None:
    width, height = 1920, 1080
    # nose at image centre, left ankle near bottom-leftish
    keypoints_px = [[0.0, 0.0]] * 17
    keypoints_px[0] = [960.0, 200.0]  # nose
    keypoints_px[15] = [900.0, 1000.0]  # left ankle
    keypoints_px[16] = [1020.0, 1000.0]  # right ankle
    scores = [0.9] * 17
    payload = {
        "predictions": [
            [
                {
                    "keypoints": keypoints_px,
                    "keypoint_scores": scores,
                    "bbox": [800.0, 100.0, 1120.0, 1040.0],
                }
            ]
        ]
    }

    class _Inferencer:
        def __call__(self, image: Any, return_vis: bool = False) -> list[dict[str, Any]]:
            del image, return_vis
            return [payload]

    backend = MMPoseBackend(inferencer=_Inferencer())
    people = backend.detect_persons(SimpleNamespace(image=SimpleNamespace(shape=(height, width, 3))))
    assert len(people) == 1
    nose = people[0].keypoints["nose"]
    assert nose.x == pytest.approx(960.0 / width)
    assert nose.y == pytest.approx(200.0 / height)
    assert people[0].keypoints["left_ankle"].visibility == pytest.approx(0.9)
    assert people[0].bbox.x_min == pytest.approx(800.0 / width)
