"""4D temporal scene: COLMAP capture cameras + rigid plane clusters (RIGS-lite)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from geom.planes import Plane, fit_planes, parse_points3d_txt
from temporal.flow_rigs import estimate_cluster_keys
from temporal.normalize import cameras_from_extrinsics


@dataclass(frozen=True)
class TemporalScene:
    enabled: bool
    frame_count: int
    duration_s: float | None
    fps: float | None
    source_kind: str
    times: tuple[float, ...]
    cameras: tuple[dict[str, Any], ...]
    clusters: tuple[dict[str, Any], ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "frameCount": self.frame_count,
            "durationS": self.duration_s,
            "fps": self.fps,
            "currentTime": 0.0,
            "sourceKind": self.source_kind,
            "times": list(self.times),
            "cameras": list(self.cameras),
            "clusters": list(self.clusters),
        }


def interpolate_offsets(
    times: list[float],
    keys: list[dict[str, Any]],
    t: float,
) -> tuple[float, float, float]:
    if not times or not keys:
        return (0.0, 0.0, 0.0)
    if t <= times[0]:
        tr = keys[0].get("t", [0.0, 0.0, 0.0])
        return (float(tr[0]), float(tr[1]), float(tr[2]))
    if t >= times[-1]:
        tr = keys[-1].get("t", [0.0, 0.0, 0.0])
        return (float(tr[0]), float(tr[1]), float(tr[2]))
    for index in range(len(times) - 1):
        t0, t1 = times[index], times[index + 1]
        if t0 <= t <= t1:
            span = t1 - t0 if t1 > t0 else 1.0
            alpha = (t - t0) / span
            a = keys[index].get("t", [0.0, 0.0, 0.0])
            b = keys[index + 1].get("t", [0.0, 0.0, 0.0])
            return (
                float(a[0]) * (1 - alpha) + float(b[0]) * alpha,
                float(a[1]) * (1 - alpha) + float(b[1]) * alpha,
                float(a[2]) * (1 - alpha) + float(b[2]) * alpha,
            )
    tr = keys[-1].get("t", [0.0, 0.0, 0.0])
    return (float(tr[0]), float(tr[1]), float(tr[2]))


def interpolate_camera(cameras: list[dict[str, Any]], t: float) -> dict[str, Any] | None:
    if not cameras:
        return None
    if t <= float(cameras[0]["t"]):
        return cameras[0]
    if t >= float(cameras[-1]["t"]):
        return cameras[-1]
    for index in range(len(cameras) - 1):
        a, b = cameras[index], cameras[index + 1]
        t0, t1 = float(a["t"]), float(b["t"])
        if t0 <= t <= t1:
            span = t1 - t0 if t1 > t0 else 1.0
            alpha = (t - t0) / span
            return {
                "t": t,
                "position": _lerp3(a["position"], b["position"], alpha),
                "target": _lerp3(a["target"], b["target"], alpha),
                "name": a.get("name", ""),
            }
    return cameras[-1]


def parse_image_extrinsics(path: Path) -> list[dict[str, Any]]:
    """COLMAP ``images.txt`` rows (name + world-to-camera quat/t), sorted by name."""
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 10:
            continue
        rows.append(
            {
                "name": parts[9],
                "qw": float(parts[1]),
                "qx": float(parts[2]),
                "qy": float(parts[3]),
                "qz": float(parts[4]),
                "tx": float(parts[5]),
                "ty": float(parts[6]),
                "tz": float(parts[7]),
            }
        )
        if index < len(lines) and not lines[index].strip().startswith("#"):
            index += 1
    rows.sort(key=lambda item: str(item["name"]))
    return rows


def parse_images_txt(path: Path, *, normalize_world_space: bool = False, points3d_txt: Path | None = None) -> list[dict[str, Any]]:
    """COLMAP ``images.txt`` → camera centers in world (Y-up after 180° X)."""
    extrinsics = parse_image_extrinsics(path)
    if not extrinsics:
        return []
    if normalize_world_space:
        points_xyz: list[tuple[float, float, float]] = []
        if points3d_txt is not None and points3d_txt.is_file():
            points_xyz = [(row[1], row[2], row[3]) for row in parse_points3d_txt(points3d_txt)]
        return cameras_from_extrinsics(extrinsics, points_xyz)
    cameras: list[dict[str, Any]] = []
    for row in extrinsics:
        center = _camera_center(row["qw"], row["qx"], row["qy"], row["qz"], row["tx"], row["ty"], row["tz"])
        look = _camera_look(row["qw"], row["qx"], row["qy"], row["qz"], center)
        cameras.append(
            {
                "name": row["name"],
                "position": [center[0], center[1], center[2]],
                "target": [look[0], look[1], look[2]],
            }
        )
    count = len(cameras)
    for cam_index, camera in enumerate(cameras):
        camera["t"] = 0.0 if count <= 1 else cam_index / (count - 1)
    return cameras


def build_temporal_scene(
    *,
    points3d_txt: Path | None,
    images_txt: Path | None,
    frame_count: int,
    duration_s: float | None,
    fps: float | None,
    source_kind: str,
    frames_dir: Path | None = None,
    normalize_world_space: bool = False,
) -> TemporalScene:
    cameras = (
        parse_images_txt(
            images_txt,
            normalize_world_space=normalize_world_space,
            points3d_txt=points3d_txt,
        )
        if images_txt is not None
        else []
    )
    times = [float(camera["t"]) for camera in cameras] or [0.0, 1.0]
    points: list[tuple[float, float, float]] = []
    if points3d_txt is not None:
        rows = parse_points3d_txt(points3d_txt)
        points = [(row[1], row[2], row[3]) for row in rows]
    planes = fit_planes(points, max_planes=4) if len(points) >= 24 else []
    motion = estimate_cluster_keys(
        planes=planes,
        cameras=cameras,
        times=times,
        frames_dir=frames_dir,
    )
    clusters = [
        _motion_cluster(plane, times, index, motion[index] if index < len(motion) else None)
        for index, plane in enumerate(planes)
    ]
    if not clusters:
        clusters = [_world_cluster(times)]
    enabled = bool(cameras) or source_kind in {"video", "gif", "sequence"} or frame_count > 1
    return TemporalScene(
        enabled=enabled,
        frame_count=max(frame_count, len(cameras), len(times)),
        duration_s=duration_s,
        fps=fps,
        source_kind=source_kind if source_kind != "none" else ("video" if enabled else "none"),
        times=tuple(times),
        cameras=tuple(cameras),
        clusters=tuple(clusters),
    )


def write_temporal_document(path: Path, scene: TemporalScene) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scene.to_document(), indent=2), encoding="utf-8")


def _motion_cluster(
    plane: Plane,
    times: list[float],
    index: int,
    keys: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    centroid = _centroid(plane.inliers)
    resolved = keys if keys else [{"t": [0.0, 0.0, 0.0], "r": [0.0, 0.0, 0.0]} for _ in times]
    def _translation(item: dict) -> tuple[float, float, float]:
        raw = item.get("t") or [0, 0, 0]
        return (float(raw[0]), float(raw[1]), float(raw[2]))

    moving = any(
        abs(t[0]) + abs(t[1]) + abs(t[2]) > 1e-6 for t in map(_translation, resolved)
    )
    return {
        "id": f"cluster-{index}",
        "kind": "rigs-rigid" if moving else "rigid-plane",
        "centroid": list(centroid),
        "normal": [plane.nx, plane.ny, plane.nz],
        "d": plane.d,
        "weight": 1.0,
        "keys": resolved,
    }


def _world_cluster(times: list[float]) -> dict[str, Any]:
    return {
        "id": "cluster-world",
        "kind": "rigid-plane",
        "centroid": [0.0, 0.0, 0.0],
        "normal": [0.0, 1.0, 0.0],
        "d": 0.0,
        "weight": 1.0,
        "keys": [{"t": [0.0, 0.0, 0.0], "r": [0.0, 0.0, 0.0]} for _ in times],
    }


def _centroid(points: tuple[tuple[float, float, float], ...]) -> tuple[float, float, float]:
    if not points:
        return (0.0, 0.0, 0.0)
    n = float(len(points))
    return (
        sum(p[0] for p in points) / n,
        sum(p[1] for p in points) / n,
        sum(p[2] for p in points) / n,
    )


def _camera_center(
    qw: float, qx: float, qy: float, qz: float, tx: float, ty: float, tz: float
) -> tuple[float, float, float]:
    # C = -R^T t  (COLMAP world-from-camera)
    r00, r01, r02, r10, r11, r12, r20, r21, r22 = _quat_to_rot(qw, qx, qy, qz)
    cx = -(r00 * tx + r10 * ty + r20 * tz)
    cy = -(r01 * tx + r11 * ty + r21 * tz)
    cz = -(r02 * tx + r12 * ty + r22 * tz)
    return _opencv_to_three(cx, cy, cz)


def _camera_look(
    qw: float, qx: float, qy: float, qz: float, center: tuple[float, float, float]
) -> tuple[float, float, float]:
    _r00, _r01, _r02, _r10, _r11, _r12, r20, r21, r22 = _quat_to_rot(qw, qx, qy, qz)
    # camera +Z in OpenCV is forward of the camera after R
    fwd = _opencv_to_three(r20, r21, r22)
    return (center[0] + fwd[0], center[1] + fwd[1], center[2] + fwd[2])


def _quat_to_rot(
    qw: float, qx: float, qy: float, qz: float
) -> tuple[float, float, float, float, float, float, float, float, float]:
    n = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz) or 1.0
    qw, qx, qy, qz = qw / n, qx / n, qy / n, qz / n
    r00 = 1 - 2 * (qy * qy + qz * qz)
    r01 = 2 * (qx * qy - qz * qw)
    r02 = 2 * (qx * qz + qy * qw)
    r10 = 2 * (qx * qy + qz * qw)
    r11 = 1 - 2 * (qx * qx + qz * qz)
    r12 = 2 * (qy * qz - qx * qw)
    r20 = 2 * (qx * qz - qy * qw)
    r21 = 2 * (qy * qz + qx * qw)
    r22 = 1 - 2 * (qx * qx + qy * qy)
    return (r00, r01, r02, r10, r11, r12, r20, r21, r22)


def _opencv_to_three(x: float, y: float, z: float) -> tuple[float, float, float]:
    # 180° around X
    return (x, -y, -z)


def _lerp3(a: Any, b: Any, alpha: float) -> list[float]:
    return [
        float(a[0]) * (1 - alpha) + float(b[0]) * alpha,
        float(a[1]) * (1 - alpha) + float(b[1]) * alpha,
        float(a[2]) * (1 - alpha) + float(b[2]) * alpha,
    ]
