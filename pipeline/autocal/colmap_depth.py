"""Sparse COLMAP depth: cameras.txt + images.txt + points3D.txt."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from autocal.depth import DepthSample


@dataclass(frozen=True)
class _Camera:
    width: int
    height: int
    fy: float
    cy_norm: float


@dataclass(frozen=True)
class _Observation:
    x: float
    y: float
    point_id: int


@dataclass(frozen=True)
class _Image:
    camera_id: int
    name: str
    qw: float
    qx: float
    qy: float
    qz: float
    tx: float
    ty: float
    tz: float
    observations: tuple[_Observation, ...]


class ColmapSparseDepth:
    def __init__(self, model_dir: Path) -> None:
        self.cameras = _parse_cameras_txt(model_dir / "cameras.txt")
        self.images = _parse_images_txt(model_dir / "images.txt")
        self.points = _parse_points3d_txt(model_dir / "points3D.txt")
        self._by_name = {image.name: image for image in self.images}
        self._by_stem = {Path(image.name).name: image for image in self.images}

    def sample(self, frame_id: str, x_norm: float, y_norm: float) -> DepthSample | None:
        image = self._by_name.get(frame_id) or self._by_stem.get(Path(frame_id).name)
        if image is None:
            return None
        camera = self.cameras.get(image.camera_id)
        if camera is None or camera.fy <= 1e-9:
            return None
        px = x_norm * camera.width
        py = y_norm * camera.height
        best_z: float | None = None
        best_dist = float("inf")
        for obs in image.observations:
            if obs.point_id < 0:
                continue
            xyz = self.points.get(obs.point_id)
            if xyz is None:
                continue
            z = _camera_z(image, xyz)
            if z <= 1e-6:
                continue
            dist = (obs.x - px) ** 2 + (obs.y - py) ** 2
            if dist < best_dist:
                best_dist = dist
                best_z = z
        if best_z is None:
            return None
        return DepthSample(
            depth_scene_units=best_z,
            focal_length_y_px=camera.fy,
            principal_point_y_norm=camera.cy_norm,
            is_heuristic=False,
        )


def _parse_cameras_txt(path: Path) -> dict[int, _Camera]:
    if not path.is_file():
        return {}
    cameras: dict[int, _Camera] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        camera_id = int(parts[0])
        model = parts[1].upper()
        width, height = int(parts[2]), int(parts[3])
        params = [float(item) for item in parts[4:]]
        fy, cy = _fy_cy(model, params, height)
        cameras[camera_id] = _Camera(width=width, height=height, fy=fy, cy_norm=cy / height if height else 0.5)
    return cameras


def _fy_cy(model: str, params: list[float], height: int) -> tuple[float, float]:
    if model in {"SIMPLE_PINHOLE", "SIMPLE_RADIAL", "SIMPLE_RADIAL_FISHEYE"}:
        f = params[0] if params else float(height)
        cy = params[2] if len(params) > 2 else height / 2.0
        return (f, cy)
    if model in {"PINHOLE", "OPENCV", "OPENCV_FISHEYE", "FULL_OPENCV", "RADIAL"}:
        fy = params[1] if len(params) > 1 else (params[0] if params else float(height))
        cy = params[3] if len(params) > 3 else height / 2.0
        return (fy, cy)
    f = params[0] if params else float(height)
    return (f, height / 2.0)


def _parse_images_txt(path: Path) -> list[_Image]:
    if not path.is_file():
        return []
    images: list[_Image] = []
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
        camera_id = int(parts[8])
        name = parts[9]
        observations: list[_Observation] = []
        if index < len(lines) and not lines[index].strip().startswith("#"):
            obs_parts = lines[index].split()
            index += 1
            for cursor in range(0, len(obs_parts) - 2, 3):
                x = float(obs_parts[cursor])
                y = float(obs_parts[cursor + 1])
                point_id = int(float(obs_parts[cursor + 2]))
                observations.append(_Observation(x=x, y=y, point_id=point_id))
        images.append(
            _Image(
                camera_id=camera_id,
                name=name,
                qw=float(parts[1]),
                qx=float(parts[2]),
                qy=float(parts[3]),
                qz=float(parts[4]),
                tx=float(parts[5]),
                ty=float(parts[6]),
                tz=float(parts[7]),
                observations=tuple(observations),
            )
        )
    return images


def _parse_points3d_txt(path: Path) -> dict[int, tuple[float, float, float]]:
    if not path.is_file():
        return {}
    points: dict[int, tuple[float, float, float]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        points[int(parts[0])] = (float(parts[1]), float(parts[2]), float(parts[3]))
    return points


def _camera_z(image: _Image, xyz: tuple[float, float, float]) -> float:
    r00, r01, r02, r10, r11, r12, r20, r21, r22 = _quat_to_rot(image.qw, image.qx, image.qy, image.qz)
    x, y, z = xyz
    return r20 * x + r21 * y + r22 * z + image.tz


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
