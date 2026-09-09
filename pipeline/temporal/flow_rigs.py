"""RIGS-lite: residual planar motion from frame-to-frame flow."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from geom.planes import Plane


def estimate_cluster_keys(
    *,
    planes: list[Plane],
    cameras: list[dict[str, Any]],
    times: list[float],
    frames_dir: Path | None,
) -> list[list[dict[str, Any]]]:
    """One key list per plane. Identity when frames/flow are missing."""
    if not planes:
        return []
    static = [[{"t": [0.0, 0.0, 0.0], "r": [0.0, 0.0, 0.0]} for _ in times] for _ in planes]
    if frames_dir is None or not frames_dir.is_dir() or len(cameras) < 2 or len(times) < 2:
        return static
    grays = _load_camera_grays(cameras, frames_dir)
    if len(grays) < 2:
        return static
    keys: list[list[dict[str, Any]]] = []
    for plane in planes:
        series = [[0.0, 0.0, 0.0] for _ in times]
        acc = [0.0, 0.0, 0.0]
        for index in range(len(times) - 1):
            a = cameras[min(index, len(cameras) - 1)]
            b = cameras[min(index + 1, len(cameras) - 1)]
            name_a = str(a.get("name", ""))
            name_b = str(b.get("name", ""))
            img_a = grays.get(name_a)
            img_b = grays.get(name_b)
            if img_a is None or img_b is None:
                series[index + 1] = list(acc)
                continue
            residual = _plane_residual_translation(plane, a, b, img_a, img_b)
            acc = [acc[0] + residual[0], acc[1] + residual[1], acc[2] + residual[2]]
            series[index + 1] = list(acc)
        keys.append([{"t": xyz, "r": [0.0, 0.0, 0.0]} for xyz in series])
    return keys


def write_4dgs_npz(path: Path, times: list[float], trajectories: list[list[list[float]]]) -> None:
    """Video2-style interchange: times + trajectories [C, T, 3]."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import numpy as np
    except ImportError:
        path.with_suffix(".json").write_text(
            __import__("json").dumps({"times": times, "trajectories": trajectories}),
            encoding="utf-8",
        )
        return
    packed = np.asarray(trajectories, dtype=np.float32)
    np.savez_compressed(path, times=np.asarray(times, dtype=np.float32), trajectories=packed)


def _load_camera_grays(cameras: list[dict[str, Any]], frames_dir: Path) -> dict[str, list[list[int]]]:
    loaded: dict[str, list[list[int]]] = {}
    for camera in cameras:
        name = str(camera.get("name", ""))
        if not name:
            continue
        candidate = frames_dir / Path(name).name
        if not candidate.is_file():
            matches = list(frames_dir.glob(Path(name).stem + ".*"))
            candidate = matches[0] if matches else candidate
        gray = _load_gray(candidate)
        if gray is not None:
            loaded[name] = gray
    return loaded


def _load_gray(path: Path) -> list[list[int]] | None:
    if not path.is_file():
        return None
    suffix = path.suffix.lower()
    if suffix == ".pgm":
        return _load_pgm(path)
    try:
        from PIL import Image
    except ImportError:
        return None
    image = Image.open(path).convert("L")
    width, height = image.size
    if width > 320 or height > 240:
        image.thumbnail((320, 240))
        width, height = image.size
    pixels = list(image.getdata())
    return [pixels[row * width : (row + 1) * width] for row in range(height)]


def _load_pgm(path: Path) -> list[list[int]] | None:
    data = path.read_bytes()
    if not data.startswith(b"P2") and not data.startswith(b"P5"):
        return None
    if data.startswith(b"P5"):
        header, _, rest = data.partition(b"\n")
        body = rest
        while body.startswith(b"#"):
            _, _, body = body.partition(b"\n")
        dims, _, body = body.partition(b"\n")
        _maxv, _, raw = body.partition(b"\n")
        width, height = (int(part) for part in dims.split())
        pixels = list(raw[: width * height])
        return [pixels[row * width : (row + 1) * width] for row in range(height)]
    text = data.decode("ascii", "replace").splitlines()
    tokens: list[str] = []
    for line in text:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        tokens.extend(stripped.split())
    if len(tokens) < 4 or tokens[0] != "P2":
        return None
    width, height = int(tokens[1]), int(tokens[2])
    values = [int(token) for token in tokens[4 : 4 + width * height]]
    return [values[row * width : (row + 1) * width] for row in range(height)]


def _plane_residual_translation(
    plane: Plane,
    cam_a: dict[str, Any],
    cam_b: dict[str, Any],
    img_a: list[list[int]],
    img_b: list[list[int]],
) -> tuple[float, float, float]:
    height = len(img_a)
    width = len(img_a[0]) if height else 0
    if width < 16 or height < 16:
        return (0.0, 0.0, 0.0)
    samples = plane.inliers[:12] or ((0.0, 0.0, 0.0),)
    residuals: list[tuple[float, float]] = []
    for point in samples:
        u0, v0 = _project(point, cam_a, width, height)
        pred_u, pred_v = _project(point, cam_b, width, height)
        found = _patch_flow(img_a, img_b, u0, v0)
        if found is None:
            continue
        residuals.append((found[0] - pred_u, found[1] - pred_v))
    if len(residuals) < 3:
        return (0.0, 0.0, 0.0)
    residuals.sort(key=lambda item: item[0] ** 2 + item[1] ** 2)
    mid = residuals[len(residuals) // 2]
    # Pixel residual → world using a conservative focal and look vector.
    focal = 0.7 * max(width, height)
    scale = 0.35 / max(focal, 1.0)
    look = _look_vector(cam_a)
    right = _normalize((-look[2], 0.0, look[0])) or (1.0, 0.0, 0.0)
    up = (0.0, 1.0, 0.0)
    dx = mid[0] * scale
    dy = -mid[1] * scale
    return (
        right[0] * dx + up[0] * dy,
        right[1] * dx + up[1] * dy,
        right[2] * dx + up[2] * dy,
    )


def _project(
    point: tuple[float, float, float],
    camera: dict[str, Any],
    width: int,
    height: int,
) -> tuple[float, float]:
    pos = camera.get("position") or [0.0, 0.0, 0.0]
    target = camera.get("target") or [0.0, 0.0, -1.0]
    look = _normalize((target[0] - pos[0], target[1] - pos[1], target[2] - pos[2])) or (
        0.0,
        0.0,
        -1.0,
    )
    rel = (point[0] - float(pos[0]), point[1] - float(pos[1]), point[2] - float(pos[2]))
    z = rel[0] * look[0] + rel[1] * look[1] + rel[2] * look[2]
    if z <= 1e-4:
        z = 1e-4
    right = _normalize((-look[2], 0.0, look[0])) or (1.0, 0.0, 0.0)
    up = _normalize(_cross(right, look)) or (0.0, 1.0, 0.0)
    x = rel[0] * right[0] + rel[1] * right[1] + rel[2] * right[2]
    y = rel[0] * up[0] + rel[1] * up[1] + rel[2] * up[2]
    focal = 0.7 * max(width, height)
    u = width * 0.5 + (x / z) * focal
    v = height * 0.5 - (y / z) * focal
    return (u, v)


def _patch_flow(
    img_a: list[list[int]],
    img_b: list[list[int]],
    u: float,
    v: float,
    radius: int = 4,
    search: int = 8,
) -> tuple[float, float] | None:
    height = len(img_a)
    width = len(img_a[0])
    cx, cy = int(round(u)), int(round(v))
    if cx < radius or cy < radius or cx >= width - radius or cy >= height - radius:
        return None
    best = 1e18
    best_uv = (float(cx), float(cy))
    for dy in range(-search, search + 1, 2):
        for dx in range(-search, search + 1, 2):
            tx, ty = cx + dx, cy + dy
            if tx < radius or ty < radius or tx >= width - radius or ty >= height - radius:
                continue
            score = 0
            for py in range(-radius, radius + 1):
                row_a = img_a[cy + py]
                row_b = img_b[ty + py]
                for px in range(-radius, radius + 1):
                    score += abs(row_a[cx + px] - row_b[tx + px])
            if score < best:
                best = score
                best_uv = (float(tx), float(ty))
    return best_uv


def _look_vector(camera: dict[str, Any]) -> tuple[float, float, float]:
    pos = camera.get("position") or [0.0, 0.0, 0.0]
    target = camera.get("target") or [0.0, 0.0, -1.0]
    return _normalize((target[0] - pos[0], target[1] - pos[1], target[2] - pos[2])) or (
        0.0,
        0.0,
        -1.0,
    )


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float] | None:
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length < 1e-8:
        return None
    return (v[0] / length, v[1] / length, v[2] / length)
