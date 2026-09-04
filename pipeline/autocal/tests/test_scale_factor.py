"""Scale-factor aggregation: definition, weighted median, error bar."""

from __future__ import annotations

import pytest

from autocal.scale_factor import aggregate_scale_factors


def test_scale_is_user_height_over_scene_height() -> None:
    result = aggregate_scale_factors(1.75, [2.5])
    assert result.scale_factor == pytest.approx(0.7)
    assert result.n_samples == 1
    assert result.error_estimate == pytest.approx(0.7 * 0.20)


def test_weighted_median_ignores_low_weight_outlier() -> None:
    # Three consistent votes around 0.70 and one absurd 2.0 with tiny weight.
    scene_heights = [1.75 / 0.70, 1.75 / 0.71, 1.75 / 0.69, 1.75 / 2.0]
    weights = [1.0, 1.0, 1.0, 0.01]
    result = aggregate_scale_factors(1.75, scene_heights, weights)
    assert result.scale_factor == pytest.approx(0.70, abs=0.02)
    assert result.error_estimate > 0.0


def test_identical_samples_have_zero_robust_error() -> None:
    result = aggregate_scale_factors(1.80, [3.0, 3.0, 3.0, 3.0])
    assert result.scale_factor == pytest.approx(1.80 / 3.0)
    assert result.error_estimate == pytest.approx(0.0)


def test_two_samples_error_is_half_gap() -> None:
    result = aggregate_scale_factors(2.0, [2.0, 4.0])
    # scales = 1.0 and 0.5; half gap = 0.25
    assert result.error_estimate == pytest.approx(0.25)


def test_rejects_non_positive_user_height() -> None:
    with pytest.raises(ValueError, match="user_height_meters"):
        aggregate_scale_factors(0.0, [2.0])


def test_rejects_empty_scene_heights() -> None:
    with pytest.raises(ValueError, match="scene_heights"):
        aggregate_scale_factors(1.7, [])
