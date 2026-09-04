"""Stdlib point-cloud cleanup for Gaussian centres.

No NumPy. Neighbour queries use a spatial hash (uniform grid). Pipeline:

1. Drop Gaussians whose activated opacity is below ``opacity_threshold``.
   3DGS stores ``opacity`` as a **logit**; activation is the logistic
   sigmoid ``σ(x) = 1 / (1 + e^{-x})``.
2. Statistical outlier removal (Open3D-compatible): for each point compute
   the mean Euclidean distance ``d_i`` to its ``k`` nearest neighbours.
   Let ``μ``, ``σ`` be the mean and population stdev of ``{d_i}``. Keep
   ``i`` iff ``d_i ≤ μ + std_ratio · σ``.
3. Density percentile cut: treat ``ρ_i = 1 / (d_i + ε)`` as a density
   estimate. Drop the lowest ``density_percentile`` fraction of ``ρ``.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from .types import Vec3

DEFAULT_KNN_K: int = 16
DEFAULT_STD_RATIO: float = 2.0
DEFAULT_DENSITY_PERCENTILE: float = 0.1
DEFAULT_OPACITY_THRESHOLD: float = 0.005
_EPS: float = 1e-12


@dataclass(frozen=True, slots=True)
class FilterResult:
    """Subset of an input cloud after opacity / outlier / density cuts."""

    points: tuple[Vec3, ...]
    kept_indices: tuple[int, ...]
    points_in: int
    points_filtered: int
    removed_opacity: int
    removed_outlier: int
    removed_density: int


def opacity_sigmoid(logit: float) -> float:
    """Numerically stable logistic sigmoid (3DGS opacity activation)."""
    if logit >= 0.0:
        return 1.0 / (1.0 + math.exp(-logit))
    exp_x = math.exp(logit)
    return exp_x / (1.0 + exp_x)


def inverse_opacity_sigmoid(probability: float) -> float:
    """Inverse sigmoid, clamped away from {0, 1}."""
    clamped = min(1.0 - 1e-6, max(1e-6, probability))
    return math.log(clamped / (1.0 - clamped))


def quantile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile. ``q`` is in ``[0, 1]``."""
    if not values:
        raise ValueError("quantile requires at least one value")
    if q <= 0.0:
        return min(values)
    if q >= 1.0:
        return max(values)
    ordered = sorted(values)
    index = q * (len(ordered) - 1)
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    frac = index - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def knn_neighbors(
    points: Sequence[Vec3],
    k: int,
) -> list[tuple[tuple[float, int], ...]]:
    """``k`` nearest neighbours of each point (self excluded).

    Returns a list aligned with ``points``. Each entry is
    ``((distance, index), ...)`` sorted by ascending distance.
    """
    count = len(points)
    if count == 0:
        return []
    k_eff = min(k, count - 1)
    if k_eff < 1:
        return [() for _ in points]

    cell = _suggested_cell_size(points)
    grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    keys: list[tuple[int, int, int]] = []
    for index, point in enumerate(points):
        key = (
            math.floor(point[0] / cell),
            math.floor(point[1] / cell),
            math.floor(point[2] / cell),
        )
        grid[key].append(index)
        keys.append(key)
    occupied = tuple(grid.keys())

    result: list[tuple[tuple[float, int], ...]] = []
    for index, point in enumerate(points):
        cx, cy, cz = keys[index]
        ordered_cells = sorted(
            occupied,
            key=lambda item: max(abs(item[0] - cx), abs(item[1] - cy), abs(item[2] - cz)),
        )
        found: list[tuple[float, int]] = []
        for key in ordered_cells:
            cheb = max(abs(key[0] - cx), abs(key[1] - cy), abs(key[2] - cz))
            if len(found) >= k_eff:
                found.sort()
                kth = found[k_eff - 1][0]
                min_remaining = max(0.0, (cheb - 1) * cell)
                if kth <= min_remaining:
                    break
            for other in grid[key]:
                if other == index:
                    continue
                found.append((_euclidean(point, points[other]), other))
        found.sort()
        result.append(tuple(found[:k_eff]))
    return result


def mean_knn_distances(points: Sequence[Vec3], k: int) -> list[float]:
    """Mean Euclidean distance from each point to its ``k`` nearest neighbours."""
    neighbours = knn_neighbors(points, k)
    means: list[float] = []
    for row in neighbours:
        if not row:
            means.append(0.0)
            continue
        means.append(sum(distance for distance, _index in row) / len(row))
    return means


def statistical_keep_mask(
    points: Sequence[Vec3],
    *,
    knn_k: int = DEFAULT_KNN_K,
    std_ratio: float = DEFAULT_STD_RATIO,
) -> list[bool]:
    """``True`` where ``d_i ≤ μ + std_ratio · σ`` (population σ)."""
    count = len(points)
    if count < 3:
        return [True] * count
    distances = mean_knn_distances(points, knn_k)
    centre = statistics.fmean(distances)
    spread = statistics.pstdev(distances) if count > 1 else 0.0
    limit = centre + std_ratio * spread
    return [distance <= limit for distance in distances]


def density_keep_mask(
    points: Sequence[Vec3],
    *,
    knn_k: int = DEFAULT_KNN_K,
    density_percentile: float = DEFAULT_DENSITY_PERCENTILE,
) -> list[bool]:
    """``True`` where local density is at or above the given percentile."""
    count = len(points)
    if count == 0 or density_percentile <= 0.0:
        return [True] * count
    if density_percentile >= 1.0:
        return [False] * count
    distances = mean_knn_distances(points, knn_k)
    densities = [1.0 / (distance + _EPS) for distance in distances]
    cutoff = quantile(densities, density_percentile)
    return [density >= cutoff for density in densities]


def estimate_normals(
    points: Sequence[Vec3],
    *,
    knn_k: int = DEFAULT_KNN_K,
) -> tuple[Vec3, ...]:
    """Local PCA normals (smallest eigenvector of the neighbour covariance).

    Orientation heuristic: flip so ``n · (centroid − p) ≥ 0`` (inward for
    indoor walkthroughs, where cameras sit near the scene centroid).
    """
    count = len(points)
    if count == 0:
        return ()
    centroid = _centroid(points)
    neighbours = knn_neighbors(points, knn_k)
    normals: list[Vec3] = []
    for index, point in enumerate(points):
        sample = [point, *[points[other] for _dist, other in neighbours[index]]]
        normal = _pca_normal(sample)
        to_centre = (
            centroid[0] - point[0],
            centroid[1] - point[1],
            centroid[2] - point[2],
        )
        if _dot(normal, to_centre) < 0.0:
            normal = (-normal[0], -normal[1], -normal[2])
        normals.append(normal)
    return tuple(normals)


def normals_are_usable(normals: Sequence[Vec3] | None) -> bool:
    """False when missing or (classic 3DGS) written as all zeros."""
    if not normals:
        return False
    good = sum(1 for normal in normals if _length_sq(normal) > 1e-12)
    return good >= max(1, len(normals) // 2)


def filter_cloud(
    points: Sequence[Vec3],
    *,
    opacities: Sequence[float] | None = None,
    knn_k: int = DEFAULT_KNN_K,
    std_ratio: float = DEFAULT_STD_RATIO,
    density_percentile: float = DEFAULT_DENSITY_PERCENTILE,
    opacity_threshold: float = DEFAULT_OPACITY_THRESHOLD,
) -> FilterResult:
    """Run opacity → statistical outlier → density percentile, in that order."""
    incoming = len(points)
    kept = list(range(incoming))
    removed_opacity = 0
    if opacities is not None:
        if len(opacities) != incoming:
            raise ValueError("opacities must align with points")
        after = [
            index
            for index in kept
            if opacity_sigmoid(opacities[index]) >= opacity_threshold
        ]
        removed_opacity = len(kept) - len(after)
        kept = after

    removed_outlier = 0
    subset = [points[index] for index in kept]
    if subset:
        mask = statistical_keep_mask(subset, knn_k=knn_k, std_ratio=std_ratio)
        after = [index for index, keep in zip(kept, mask, strict=True) if keep]
        removed_outlier = len(kept) - len(after)
        kept = after

    removed_density = 0
    subset = [points[index] for index in kept]
    if subset:
        mask = density_keep_mask(
            subset,
            knn_k=knn_k,
            density_percentile=density_percentile,
        )
        after = [index for index, keep in zip(kept, mask, strict=True) if keep]
        removed_density = len(kept) - len(after)
        kept = after

    return FilterResult(
        points=tuple(points[index] for index in kept),
        kept_indices=tuple(kept),
        points_in=incoming,
        points_filtered=len(kept),
        removed_opacity=removed_opacity,
        removed_outlier=removed_outlier,
        removed_density=removed_density,
    )


def _suggested_cell_size(points: Sequence[Vec3]) -> float:
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    min_z = min(point[2] for point in points)
    max_z = max(point[2] for point in points)
    extent = max(max_x - min_x, max_y - min_y, max_z - min_z, _EPS)
    return max(extent / max(len(points) ** (1.0 / 3.0), 1.0), _EPS)


def _euclidean(left: Vec3, right: Vec3) -> float:
    dx = left[0] - right[0]
    dy = left[1] - right[1]
    dz = left[2] - right[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _centroid(points: Sequence[Vec3]) -> Vec3:
    count = len(points)
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def _dot(left: Vec3, right: Vec3) -> float:
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def _length_sq(vector: Vec3) -> float:
    return vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2]


def _normalize(vector: Vec3) -> Vec3:
    norm = math.sqrt(_length_sq(vector))
    if norm < _EPS:
        return (0.0, 0.0, 1.0)
    return (vector[0] / norm, vector[1] / norm, vector[2] / norm)


def _pca_normal(sample: Sequence[Vec3]) -> Vec3:
    if len(sample) < 3:
        return (0.0, 0.0, 1.0)
    centre = _centroid(sample)
    cxx = cxy = cxz = cyy = cyz = czz = 0.0
    for point in sample:
        dx = point[0] - centre[0]
        dy = point[1] - centre[1]
        dz = point[2] - centre[2]
        cxx += dx * dx
        cxy += dx * dy
        cxz += dx * dz
        cyy += dy * dy
        cyz += dy * dz
        czz += dz * dz
    scale = 1.0 / len(sample)
    return _smallest_eigenvector(
        cxx * scale,
        cxy * scale,
        cxz * scale,
        cyy * scale,
        cyz * scale,
        czz * scale,
    )


def _smallest_eigenvector(
    cxx: float,
    cxy: float,
    cxz: float,
    cyy: float,
    cyz: float,
    czz: float,
) -> Vec3:
    """Inverse iteration on the 3×3 covariance (evals ≥ 0)."""
    vector: Vec3 = (0.0, 0.0, 1.0)
    for _ in range(20):
        vector = _normalize(
            _solve_sym3(cxx, cxy, cxz, cyy, cyz, czz, *vector)
        )
    return vector


def _solve_sym3(
    cxx: float,
    cxy: float,
    cxz: float,
    cyy: float,
    cyz: float,
    czz: float,
    bx: float,
    by: float,
    bz: float,
) -> Vec3:
    """Solve a regularised symmetric 3×3 system via the explicit inverse."""
    cxx += 1e-9
    cyy += 1e-9
    czz += 1e-9
    det = (
        cxx * (cyy * czz - cyz * cyz)
        - cxy * (cxy * czz - cxz * cyz)
        + cxz * (cxy * cyz - cxz * cyy)
    )
    if abs(det) < 1e-18:
        return (bx, by, bz)
    inv_xx = (cyy * czz - cyz * cyz) / det
    inv_xy = (cxz * cyz - cxy * czz) / det
    inv_xz = (cxy * cyz - cxz * cyy) / det
    inv_yy = (cxx * czz - cxz * cxz) / det
    inv_yz = (cxy * cxz - cxx * cyz) / det
    inv_zz = (cxx * cyy - cxy * cxy) / det
    return (
        inv_xx * bx + inv_xy * by + inv_xz * bz,
        inv_xy * bx + inv_yy * by + inv_yz * bz,
        inv_xz * bx + inv_yz * by + inv_zz * bz,
    )
