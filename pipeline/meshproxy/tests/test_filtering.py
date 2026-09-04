"""Outlier hash, opacity sigmoid and density percentile — no NumPy."""

from __future__ import annotations

import math

import pytest
from pipeline.meshproxy.filtering import (
    density_keep_mask,
    estimate_normals,
    filter_cloud,
    knn_neighbors,
    mean_knn_distances,
    opacity_sigmoid,
    statistical_keep_mask,
)


def _brute_knn(
    points: list[tuple[float, float, float]],
    k: int,
) -> list[list[tuple[float, int]]]:
    result: list[list[tuple[float, int]]] = []
    for index, point in enumerate(points):
        row: list[tuple[float, int]] = []
        for other, candidate in enumerate(points):
            if other == index:
                continue
            dx = point[0] - candidate[0]
            dy = point[1] - candidate[1]
            dz = point[2] - candidate[2]
            row.append((math.sqrt(dx * dx + dy * dy + dz * dz), other))
        row.sort()
        result.append(row[:k])
    return result


def test_opacity_sigmoid_known_values() -> None:
    assert opacity_sigmoid(0.0) == pytest.approx(0.5)
    assert opacity_sigmoid(2.0) == pytest.approx(1.0 / (1.0 + math.exp(-2.0)))
    assert opacity_sigmoid(-10.0) == pytest.approx(4.53978687024e-5, rel=1e-6)
    assert 0.0 < opacity_sigmoid(-50.0) < 1e-20
    assert opacity_sigmoid(50.0) == pytest.approx(1.0)


def test_opacity_threshold_drops_transparent_gaussians() -> None:
    points = [(float(index), 0.0, 0.0) for index in range(6)]
    # logits: three nearly transparent, three opaque
    opacities = [-10.0, -8.0, -6.0, 2.0, 3.0, 4.0]
    result = filter_cloud(
        points,
        opacities=opacities,
        knn_k=2,
        std_ratio=100.0,
        density_percentile=0.0,
        opacity_threshold=0.01,
    )
    assert result.removed_opacity == 3
    assert result.points_filtered == 3
    assert result.kept_indices == (3, 4, 5)
    for logit in (2.0, 3.0, 4.0):
        assert opacity_sigmoid(logit) >= 0.01
    for logit in (-10.0, -8.0, -6.0):
        assert opacity_sigmoid(logit) < 0.01


def test_spatial_hash_knn_matches_brute_force() -> None:
    points = [
        (float(x), float(y), float(z))
        for x in range(4)
        for y in range(4)
        for z in range(2)
    ]
    hashed = knn_neighbors(points, 5)
    brute = _brute_knn(points, 5)
    for got, expected in zip(hashed, brute, strict=True):
        assert [item[1] for item in got] == [item[1] for item in expected]
        for (d_got, _), (d_exp, _) in zip(got, expected, strict=True):
            assert d_got == pytest.approx(d_exp)


def test_statistical_outliers_remove_isolated_points() -> None:
    cluster = [
        (float(x), float(y), float(z))
        for x in range(4)
        for y in range(4)
        for z in range(4)
    ]
    isolated = [(80.0, 80.0, 80.0), (-90.0, 0.0, 0.0)]
    points = cluster + isolated
    mask = statistical_keep_mask(points, knn_k=8, std_ratio=2.0)
    kept = [point for point, keep in zip(points, mask, strict=True) if keep]
    dropped = [point for point, keep in zip(points, mask, strict=True) if not keep]
    assert isolated[0] in dropped
    assert isolated[1] in dropped
    assert len(kept) == len(cluster)
    means = mean_knn_distances(points, 8)
    assert means[-1] > 10.0
    assert means[0] < 3.0


def test_filter_cloud_pipeline_counts_isolated() -> None:
    cluster = [
        (float(x), float(y), 0.0) for x in range(5) for y in range(5)
    ]
    points = cluster + [(100.0, 100.0, 0.0)]
    result = filter_cloud(
        points,
        knn_k=6,
        std_ratio=2.0,
        density_percentile=0.0,
        opacity_threshold=0.0,
    )
    assert result.points_in == 26
    assert result.removed_outlier == 1
    assert result.points_filtered == 25
    assert (100.0, 100.0, 0.0) not in result.points


def test_density_percentile_drops_the_lowest_fraction() -> None:
    dense = [(float(x) * 0.1, float(y) * 0.1, 0.0) for x in range(10) for y in range(10)]
    sparse = [(20.0 + float(i), 0.0, 0.0) for i in range(10)]
    points = dense + sparse
    mask = density_keep_mask(points, knn_k=6, density_percentile=0.1)
    kept = sum(1 for keep in mask if keep)
    # 10% of 110 → about 11 dropped; allow a small interpolation slack.
    assert 90 <= kept <= 105
    assert mask[-1] is False


def test_estimate_normals_on_xy_plane_are_vertical() -> None:
    points = [(float(x), float(y), 0.0) for x in range(6) for y in range(6)]
    normals = estimate_normals(points, knn_k=8)
    assert len(normals) == 36
    for normal in normals:
        assert abs(normal[2]) == pytest.approx(1.0, abs=0.15)
        length = math.sqrt(sum(component * component for component in normal))
        assert length == pytest.approx(1.0, abs=0.05)
