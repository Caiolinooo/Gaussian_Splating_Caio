"""Confidence score: no person → 0; partial → low; ideal → high."""

from __future__ import annotations

import pytest
from synthetic import IMAGE_HEIGHT, IMAGE_WIDTH, make_person, standing_keypoints

from autocal.confidence import ConfidenceInputs, confidence_inputs_from_estimate, score_confidence
from autocal.depth import ConstantDepthProvider
from autocal.height_estimator import PoseFrame, estimate_person_height


def test_no_person_is_zero() -> None:
    score = score_confidence(
        ConfidenceInputs(
            n_frames_total=10,
            n_frames_with_person=0,
            n_valid=0,
            full_body_ratio=0.0,
            mean_visibility=0.0,
            height_cv=0.0,
            multi_person_ratio=0.0,
            used_heuristic_depth=False,
        )
    )
    assert score == 0.0


def test_partial_body_without_valid_frames_is_low() -> None:
    score = score_confidence(
        ConfidenceInputs(
            n_frames_total=10,
            n_frames_with_person=10,
            n_valid=0,
            full_body_ratio=0.2,
            mean_visibility=0.4,
            height_cv=0.0,
            multi_person_ratio=0.0,
            used_heuristic_depth=False,
        )
    )
    assert score == 0.0
    assert score < 0.45


def test_ideal_inputs_are_high() -> None:
    score = score_confidence(
        ConfidenceInputs(
            n_frames_total=12,
            n_frames_with_person=12,
            n_valid=12,
            full_body_ratio=1.0,
            mean_visibility=0.96,
            height_cv=0.02,
            multi_person_ratio=0.0,
            used_heuristic_depth=False,
        )
    )
    assert score > 0.75


def test_heuristic_depth_lowers_an_otherwise_ideal_score() -> None:
    kwargs = {
        "n_frames_total": 12,
        "n_frames_with_person": 12,
        "n_valid": 12,
        "full_body_ratio": 1.0,
        "mean_visibility": 0.96,
        "height_cv": 0.02,
        "multi_person_ratio": 0.0,
    }
    measured = score_confidence(ConfidenceInputs(**kwargs, used_heuristic_depth=False))
    guessed = score_confidence(ConfidenceInputs(**kwargs, used_heuristic_depth=True))
    assert guessed < measured
    assert guessed == pytest.approx(measured * 0.55)


def test_estimator_partial_pipeline_is_low() -> None:
    depth = ConstantDepthProvider(4.0, float(IMAGE_HEIGHT))
    partial = make_person(standing_keypoints(include_feet=False))
    frames = [
        PoseFrame(f"p{i}", IMAGE_WIDTH, IMAGE_HEIGHT, [partial]) for i in range(8)
    ]
    estimate = estimate_person_height(frames, depth_provider=depth)
    score = score_confidence(confidence_inputs_from_estimate(estimate))
    assert score < 0.45


def test_estimator_ideal_pipeline_is_high() -> None:
    depth = ConstantDepthProvider(4.0, float(IMAGE_HEIGHT))
    person = make_person()
    frames = [PoseFrame(f"i{i}", IMAGE_WIDTH, IMAGE_HEIGHT, [person]) for i in range(12)]
    estimate = estimate_person_height(frames, depth_provider=depth)
    score = score_confidence(confidence_inputs_from_estimate(estimate))
    assert score > 0.75
