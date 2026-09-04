"""Service orchestration: never raises on missing people; warnings in pt-BR."""

from __future__ import annotations

import pytest
from synthetic import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    make_frame,
    make_person,
    standing_frames,
    standing_keypoints,
)

from autocal.depth import ConstantDepthProvider
from autocal.height_estimator import measure_pixel_stature
from autocal.messages import (
    WARN_MULTI_PERSON,
    WARN_NO_BACKEND,
    WARN_NO_DEPTH,
    WARN_NO_PERSON,
    WARN_PARTIAL_BODY,
)
from autocal.service import run_auto_calibration

DEPTH = ConstantDepthProvider(depth_scene_units=4.0, focal_length_y_px=float(IMAGE_HEIGHT))
USER_HEIGHT = 1.75


def test_no_person_returns_low_confidence_and_does_not_raise() -> None:
    frames = [make_frame(f"empty{i}", []) for i in range(5)]
    result = run_auto_calibration(frames, USER_HEIGHT, depth_provider=DEPTH)
    assert result.confidence == 0.0
    assert result.scale_factor == 1.0
    assert result.source == "auto-height"
    assert result.frames_used == 0
    assert WARN_NO_PERSON in result.warnings
    assert any("trena" in warning for warning in result.warnings)


def test_empty_frame_list_does_not_raise() -> None:
    result = run_auto_calibration([], USER_HEIGHT, depth_provider=DEPTH)
    assert result.confidence == 0.0
    assert any("trena" in warning for warning in result.warnings)


def test_ideal_frames_produce_expected_scale() -> None:
    frames = standing_frames(12)
    person = make_person()
    stature = measure_pixel_stature(person, IMAGE_WIDTH, IMAGE_HEIGHT)
    assert stature is not None
    expected_height = stature.pixel_height * 4.0 / float(IMAGE_HEIGHT)
    expected_scale = USER_HEIGHT / expected_height

    result = run_auto_calibration(frames, USER_HEIGHT, depth_provider=DEPTH)
    assert result.source == "auto-height"
    assert result.frames_used == 12
    assert result.confidence > 0.75
    assert result.scale_factor == pytest.approx(expected_scale)
    assert result.estimated_person_height_scene_units == pytest.approx(expected_height)
    assert result.error_estimate == pytest.approx(0.0)
    assert result.to_scene_dict()["scaleFactor"] == pytest.approx(expected_scale)


def test_partial_body_is_low_confidence_with_pt_br_warning() -> None:
    partial = make_person(standing_keypoints(include_feet=False))
    frames = [make_frame(f"part{i}", [partial]) for i in range(8)]
    result = run_auto_calibration(frames, USER_HEIGHT, depth_provider=DEPTH)
    assert result.confidence < 0.45
    assert result.scale_factor == 1.0
    assert WARN_PARTIAL_BODY in result.warnings


def test_multiple_people_emits_warning() -> None:
    primary = make_person(center_x=0.40)
    extra = make_person(center_x=0.75, shoulder_half_width=0.04)
    frames = [make_frame(f"m{i}", [primary, extra]) for i in range(10)]
    result = run_auto_calibration(frames, USER_HEIGHT, depth_provider=DEPTH)
    assert WARN_MULTI_PERSON in result.warnings
    assert result.frames_used == 10
    assert result.confidence > 0.0


def test_missing_depth_does_not_invent_a_scale() -> None:
    frames = standing_frames(8)
    result = run_auto_calibration(frames, USER_HEIGHT, depth_provider=None)
    assert result.confidence == 0.0
    assert result.scale_factor == 1.0
    assert WARN_NO_DEPTH in result.warnings


def test_no_backend_and_no_poses_warns_in_portuguese() -> None:
    frames = [make_frame("bare", None)]
    result = run_auto_calibration(frames, USER_HEIGHT, depth_provider=DEPTH)
    assert result.confidence == 0.0
    assert WARN_NO_BACKEND in result.warnings or WARN_NO_PERSON in result.warnings


def test_invalid_height_raises() -> None:
    with pytest.raises(ValueError, match="user_height_meters"):
        run_auto_calibration(standing_frames(2), 0.0, depth_provider=DEPTH)
