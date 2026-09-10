"""Match gsplat ``datasets/normalize.py`` so viewer cameras sit in the ply frame."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def _opencv_to_three(x: float, y: float, z: float) -> tuple[float, float, float]:
    return (x, -y, -z)


def _quat_to_rot(
    qw: float, qx: float, qy: float, qz: float
) -> tuple[float, float, float, float, float, float, float, float, float]:
    norm = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz) or 1.0
    qw, qx, qy, qz = qw / norm, qx / norm, qy / norm, qz / norm
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


def trainer_normalizes_world(extra_args: tuple[str, ...] | list[str]) -> bool:
    """gsplat default is True. Only an explicit False/0/no disables it."""
    args = list(extra_args)
    for index, flag in enumerate(args):
        if flag not in {"--normalize_world_space", "--normalize-world-space"}:
            continue
        if index + 1 >= len(args):
            return True
        return str(args[index + 1]).lower() not in {"false", "0", "no"}
    return True


def colmap_c2w(qw: float, qx: float, qy: float, qz: float, tx: float, ty: float, tz: float) -> np.ndarray:
    r00, r01, r02, r10, r11, r12, r20, r21, r22 = _quat_to_rot(qw, qx, qy, qz)
    rotation = np.array(
        [[r00, r01, r02], [r10, r11, r12], [r20, r21, r22]],
        dtype=np.float64,
    )
    translation = np.array([tx, ty, tz], dtype=np.float64)
    world_from_camera = np.eye(4, dtype=np.float64)
    world_from_camera[:3, :3] = rotation.T
    world_from_camera[:3, 3] = -rotation.T @ translation
    return world_from_camera


def similarity_from_cameras(c2w: np.ndarray) -> np.ndarray:
    """Copy of gsplat examples ``similarity_from_cameras`` (focus + median scale)."""
    translation = c2w[:, :3, 3]
    rotation = c2w[:, :3, :3]
    ups = np.sum(rotation * np.array([0, -1.0, 0]), axis=-1)
    world_up = np.mean(ups, axis=0)
    world_up = world_up / np.linalg.norm(world_up)
    up_camspace = np.array([0.0, -1.0, 0.0])
    cosine = float((up_camspace * world_up).sum())
    cross = np.cross(world_up, up_camspace)
    skew = np.array(
        [
            [0.0, -cross[2], cross[1]],
            [cross[2], 0.0, -cross[0]],
            [-cross[1], cross[0], 0.0],
        ]
    )
    if cosine > -1:
        align = np.eye(3) + skew + (skew @ skew) * 1 / (1 + cosine)
    else:
        align = np.array([[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    rotation = align @ rotation
    forwards = np.sum(rotation * np.array([0, 0.0, 1.0]), axis=-1)
    translation = (align @ translation[..., None])[..., 0]
    nearest = translation + (forwards * -translation).sum(-1)[:, None] * forwards
    shift = -np.median(nearest, axis=0)
    transform = np.eye(4)
    transform[:3, 3] = shift
    transform[:3, :3] = align
    scale = 1.0 / np.median(np.linalg.norm(translation + shift, axis=-1))
    transform[:3, :] *= scale
    return transform


def align_principal_axes(point_cloud: np.ndarray) -> np.ndarray:
    centroid = np.median(point_cloud, axis=0)
    translated = point_cloud - centroid
    covariance = np.cov(translated, rowvar=False)
    _eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    sort_indices = _eigenvalues.argsort()[::-1]
    eigenvectors = eigenvectors[:, sort_indices]
    if np.linalg.det(eigenvectors) < 0:
        eigenvectors[:, 0] *= -1
    rotation = eigenvectors.T
    transform = np.eye(4)
    transform[:3, :3] = rotation
    transform[:3, 3] = -rotation @ centroid
    return transform


def transform_points(matrix: np.ndarray, points: np.ndarray) -> np.ndarray:
    return points @ matrix[:3, :3].T + matrix[:3, 3]


def transform_cameras(matrix: np.ndarray, camtoworlds: np.ndarray) -> np.ndarray:
    camtoworlds = np.einsum("nij, ki -> nkj", camtoworlds, matrix)
    scaling = np.linalg.norm(camtoworlds[:, 0, :3], axis=1)
    camtoworlds[:, :3, :3] = camtoworlds[:, :3, :3] / scaling[:, None, None]
    return camtoworlds


def normalize_world(camtoworlds: np.ndarray, points: np.ndarray | None) -> np.ndarray:
    """Same T2 @ T1 (+ optional T3 flip) as gsplat ``Parser`` when normalize=True."""
    first = similarity_from_cameras(camtoworlds)
    camtoworlds = transform_cameras(first, camtoworlds)
    if points is None or len(points) == 0:
        return camtoworlds
    points = transform_points(first, points)
    second = align_principal_axes(points)
    camtoworlds = transform_cameras(second, camtoworlds)
    points = transform_points(second, points)
    if float(np.median(points[:, 2])) > float(np.mean(points[:, 2])):
        flip = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, -1.0, 0.0, 0.0],
                [0.0, 0.0, -1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )
        camtoworlds = transform_cameras(flip, camtoworlds)
    return camtoworlds


def cameras_from_extrinsics(
    extrinsics: list[dict[str, Any]],
    points_xyz: list[tuple[float, float, float]] | None,
) -> list[dict[str, Any]]:
    if not extrinsics:
        return []
    names = [str(row["name"]) for row in extrinsics]
    camtoworlds = np.stack(
        [
            colmap_c2w(row["qw"], row["qx"], row["qy"], row["qz"], row["tx"], row["ty"], row["tz"])
            for row in extrinsics
        ],
        axis=0,
    )
    points = None
    if points_xyz:
        points = np.asarray(points_xyz, dtype=np.float64)
    return cameras_from_c2w(names, normalize_world(camtoworlds, points))


def cameras_from_c2w(names: list[str], camtoworlds: np.ndarray) -> list[dict[str, Any]]:
    cameras: list[dict[str, Any]] = []
    count = len(names)
    radii = np.linalg.norm(camtoworlds[:, :3, 3], axis=1)
    look = max(2.0, float(np.median(radii)) * 0.5) if count else 2.0
    for index, name in enumerate(names):
        matrix = camtoworlds[index]
        center_cv = (float(matrix[0, 3]), float(matrix[1, 3]), float(matrix[2, 3]))
        forward_cv = (float(matrix[0, 2]), float(matrix[1, 2]), float(matrix[2, 2]))
        center = _opencv_to_three(*center_cv)
        forward = _opencv_to_three(*forward_cv)
        cameras.append(
            {
                "name": name,
                "position": [center[0], center[1], center[2]],
                "target": [
                    center[0] + forward[0] * look,
                    center[1] + forward[1] * look,
                    center[2] + forward[2] * look,
                ],
                "t": 0.0 if count <= 1 else index / (count - 1),
            }
        )
    return cameras
