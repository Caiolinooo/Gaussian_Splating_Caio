"""RANSAC planes + densify COLMAP ``points3D.txt`` (paredes sem LiDAR)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Plane:
    nx: float
    ny: float
    nz: float
    d: float
    inliers: tuple[tuple[float, float, float], ...]

    @property
    def normal(self) -> tuple[float, float, float]:
        return (self.nx, self.ny, self.nz)


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(_dot(v, v))


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float] | None:
    length = _norm(v)
    if length < 1e-8:
        return None
    return (v[0] / length, v[1] / length, v[2] / length)


def parse_points3d_txt(path: Path) -> list[tuple[int, float, float, float, int, int, int, float, str]]:
    rows: list[tuple[int, float, float, float, int, int, int, float, str]] = []
    if not path.is_file():
        return rows
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        point_id = int(parts[0])
        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
        r, g, b = int(parts[4]), int(parts[5]), int(parts[6])
        error = float(parts[7])
        track = " ".join(parts[8:])
        rows.append((point_id, x, y, z, r, g, b, error, track))
    return rows


def write_points3d_txt(
    path: Path,
    rows: list[tuple[int, float, float, float, int, int, int, float, str]],
) -> None:
    header = (
        "# 3D point list with one line of data per point:\n"
        "# POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[] as (IMAGE_ID, POINT2D_IDX)\n"
        f"# Number of points: {len(rows)}\n"
    )
    lines = [header]
    for row in rows:
        track = f" {row[8]}" if row[8] else ""
        lines.append(
            f"{row[0]} {row[1]:.8f} {row[2]:.8f} {row[3]:.8f} "
            f"{row[4]} {row[5]} {row[6]} {row[7]:.6f}{track}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")


def fit_planes(
    points: list[tuple[float, float, float]],
    *,
    max_planes: int = 4,
    dist_thresh: float = 0.05,
    min_inliers: int = 24,
    iterations: int = 80,
    rng: random.Random | None = None,
) -> list[Plane]:
    remaining = list(points)
    planes: list[Plane] = []
    rng = rng or random.Random(0)
    for _ in range(max_planes):
        if len(remaining) < min_inliers:
            break
        plane = _ransac_plane(remaining, dist_thresh, iterations, rng)
        if plane is None or len(plane.inliers) < min_inliers:
            break
        planes.append(plane)
        # inliers are value tuples; filter by distance instead
        remaining = [p for p in remaining if abs(_signed_dist(p, plane)) > dist_thresh]
    return planes


def sample_plane_points(plane: Plane, count: int, rng: random.Random | None = None) -> list[tuple[float, float, float]]:
    if not plane.inliers or count < 1:
        return []
    rng = rng or random.Random(1)
    xs = [p[0] for p in plane.inliers]
    ys = [p[1] for p in plane.inliers]
    zs = [p[2] for p in plane.inliers]
    origin = plane.inliers[0]
    tangent = _normalize(_sub(plane.inliers[min(1, len(plane.inliers) - 1)], origin))
    if tangent is None:
        tangent = (1.0, 0.0, 0.0)
    bitangent = _normalize(_cross(plane.normal, tangent))
    if bitangent is None:
        bitangent = (0.0, 1.0, 0.0)
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 0.2)
    samples: list[tuple[float, float, float]] = []
    for _ in range(count):
        u = (rng.random() - 0.5) * span
        v = (rng.random() - 0.5) * span
        px = origin[0] + tangent[0] * u + bitangent[0] * v - plane.nx * plane.d * 0.0
        py = origin[1] + tangent[1] * u + bitangent[1] * v
        pz = origin[2] + tangent[2] * u + bitangent[2] * v
        # project onto plane
        dist = _signed_dist((px, py, pz), plane)
        samples.append((px - plane.nx * dist, py - plane.ny * dist, pz - plane.nz * dist))
    return samples


def densify_points3d_txt(
    path: Path,
    *,
    samples_per_plane: int = 400,
    max_planes: int = 4,
) -> dict[str, int]:
    rows = parse_points3d_txt(path)
    points = [(row[1], row[2], row[3]) for row in rows]
    planes = fit_planes(points, max_planes=max_planes)
    next_id = (max((row[0] for row in rows), default=0)) + 1
    added = 0
    for plane in planes:
        for sample in sample_plane_points(plane, samples_per_plane):
            rows.append((next_id, sample[0], sample[1], sample[2], 180, 180, 180, 1.0, ""))
            next_id += 1
            added += 1
    if added:
        write_points3d_txt(path, rows)
    return {"input_points": len(points), "planes": len(planes), "added": added}


def _signed_dist(point: tuple[float, float, float], plane: Plane) -> float:
    return _dot(point, plane.normal) + plane.d


def _ransac_plane(
    points: list[tuple[float, float, float]],
    dist_thresh: float,
    iterations: int,
    rng: random.Random,
) -> Plane | None:
    if len(points) < 3:
        return None
    best: Plane | None = None
    for _ in range(iterations):
        a, b, c = rng.sample(points, 3)
        normal = _normalize(_cross(_sub(b, a), _sub(c, a)))
        if normal is None:
            continue
        d = -_dot(normal, a)
        inliers = [p for p in points if abs(_dot(p, normal) + d) <= dist_thresh]
        if best is None or len(inliers) > len(best.inliers):
            best = Plane(normal[0], normal[1], normal[2], d, tuple(inliers))
    return best
