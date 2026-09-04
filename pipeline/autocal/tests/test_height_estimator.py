"""Height estimator: ideal standing poses, partial bodies, IQR outliers."""

from __future__ import annotations

from synthetic import IMAGE_HEIGHT, IMAGE_WIDTH, make_person, scale_keypoints_vertical, standing_keypoints

from autocal.depth import ConstantDepthProvider
from autocal.height_estimator import (
    PoseFrame,
    estimate_person_height,
    measure_pixel_stature,
    posture_score,
)

DEPTH = ConstantDepthProvider(depth_scene_units=4.0, focal_length_y_px=float(IMAGE_HEIGHT))


def _pose_frames(people_per_frame: list[list]) -> list[PoseFrame]:
    return [
        PoseFrame(
            frame_id=f"f{index:03d}",
            width=IMAGE_WIDTH,
            height=IMAGE_HEIGHT,
            poses=poses,
        )
        for index, poses in enumerate(people_per_frame)
    ]


def test_ideal_standing_height_matches_pinhole() -> None:
    person = make_person()
    stature = measure_pixel_stature(person, IMAGE_WIDTH, IMAGE_HEIGHT)
    assert stature is not None
    assert stature.full_body_visible
    assert stature.posture_score >= 0.95

    expected_scene = stature.pixel_height * 4.0 / float(IMAGE_HEIGHT)
    estimate = estimate_person_height(_pose_frames([[person]] * 8), depth_provider=DEPTH)
    assert estimate.estimated_height_scene_units is not None
    assert estimate.n_valid == 8
    assert abs(estimate.estimated_height_scene_units - expected_scene) < 1e-6


def test_partial_body_without_feet_is_not_valid() -> None:
    partial = make_person(standing_keypoints(include_feet=False))
    stature = measure_pixel_stature(partial, IMAGE_WIDTH, IMAGE_HEIGHT)
    assert stature is None

    estimate = estimate_person_height(_pose_frames([[partial]] * 6), depth_provider=DEPTH)
    assert estimate.estimated_height_scene_units is None
    assert estimate.n_valid == 0
    assert all(obs.reject_reason == "incomplete_skeleton" for obs in estimate.observations)


def test_iqr_drops_short_outliers() -> None:
    typical = make_person()
    short = make_person(scale_keypoints_vertical(standing_keypoints(), 0.40))
    frames = _pose_frames([[typical]] * 8 + [[short]] * 2)
    estimate = estimate_person_height(frames, depth_provider=DEPTH)
    typical_stature = measure_pixel_stature(typical, IMAGE_WIDTH, IMAGE_HEIGHT)
    assert typical_stature is not None
    expected = typical_stature.pixel_height * 4.0 / float(IMAGE_HEIGHT)
    assert estimate.n_valid == 8
    assert estimate.estimated_height_scene_units is not None
    assert abs(estimate.estimated_height_scene_units - expected) < 1e-6


def test_crouch_is_rejected_by_posture_gate() -> None:
    crouched = make_person(standing_keypoints(crouch=True))
    assert posture_score(crouched.keypoints) < 0.82
    estimate = estimate_person_height(_pose_frames([[crouched]] * 5), depth_provider=DEPTH)
    assert estimate.n_valid == 0
    assert all(obs.reject_reason == "bad_posture" for obs in estimate.observations)


def test_no_depth_provider_yields_no_scene_height() -> None:
    person = make_person()
    estimate = estimate_person_height(_pose_frames([[person]] * 4), depth_provider=None)
    assert estimate.estimated_height_scene_units is None
    assert all(obs.pixel_height is not None for obs in estimate.observations)
    assert all(obs.scene_height is None for obs in estimate.observations)


def test_empty_poses_are_no_person() -> None:
    estimate = estimate_person_height(_pose_frames([[], []]), depth_provider=DEPTH)
    assert estimate.n_with_person == 0
    assert estimate.estimated_height_scene_units is None
