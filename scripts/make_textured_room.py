"""Render a textured box room + orbit frames for COLMAP/3DGS quality proof."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def _pattern(size: int, seed: int, color: tuple[int, int, int]) -> np.ndarray:
    image = Image.new("RGB", (size, size), color)
    draw = ImageDraw.Draw(image)
    cell = 16
    for y in range(0, size, cell):
        for x in range(0, size, cell):
            on = ((x + y + seed * 13) // cell) % 2 == 0
            fill = color if on else (max(0, color[0] - 70), max(0, color[1] - 70), max(0, color[2] - 70))
            draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=fill)
    for index in range(8):
        x = (seed * 17 + index * 41) % (size - 20)
        y = (seed * 29 + index * 23) % (size - 20)
        draw.ellipse((x, y, x + 18, y + 18), fill=(255, 220, 40))
    return np.asarray(image, dtype=np.uint8)


def _wall_textures() -> dict[str, np.ndarray]:
    walls = {
        "floor": (90, 90, 95),
        "ceil": (200, 200, 205),
        "north": (170, 80, 80),
        "south": (80, 140, 90),
        "east": (80, 90, 170),
        "west": (160, 140, 70),
    }
    return {name: _pattern(256, index + 3, color) for index, (name, color) in enumerate(walls.items())}


def render_frame(textures: dict[str, np.ndarray], yaw: float, size: int = 480) -> Image.Image:
    yy, xx = np.mgrid[0:size, 0:size]
    nx = (2.0 * (xx + 0.5) / size - 1.0) * 0.7
    ny = (1.0 - 2.0 * (yy + 0.5) / size) * 0.7
    eye = np.array([math.sin(yaw) * 1.15, 1.15, math.cos(yaw) * 1.15], dtype=np.float32)
    forward = np.array([-eye[0], 1.0 - eye[1], -eye[2]], dtype=np.float32)
    forward /= np.linalg.norm(forward)
    right = np.array([-forward[2], 0.0, forward[0]], dtype=np.float32)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    dirs = (
        forward[None, None, :]
        + right[None, None, :] * nx[..., None]
        + up[None, None, :] * ny[..., None]
    )
    dirs /= np.linalg.norm(dirs, axis=-1, keepdims=True)
    faces = (
        ("floor", np.array([0.0, 1.0, 0.0]), 0.0),
        ("ceil", np.array([0.0, -1.0, 0.0]), -2.4),
        ("north", np.array([0.0, 0.0, 1.0]), -2.2),
        ("south", np.array([0.0, 0.0, -1.0]), -2.2),
        ("east", np.array([-1.0, 0.0, 0.0]), -2.2),
        ("west", np.array([1.0, 0.0, 0.0]), -2.2),
    )
    best_t = np.full((size, size), 1e9, dtype=np.float32)
    face_id = np.zeros((size, size), dtype=np.int32)
    uu = np.zeros((size, size), dtype=np.float32)
    vv = np.zeros((size, size), dtype=np.float32)
    for index, (name, normal, d) in enumerate(faces, start=1):
        denom = dirs @ normal
        valid = np.abs(denom) > 1e-6
        t = np.full((size, size), 1e9, dtype=np.float32)
        t[valid] = -((eye @ normal) + d) / denom[valid]
        hit = eye[None, None, :] + dirs * t[..., None]
        inside = (
            (t > 1e-4)
            & (np.abs(hit[..., 0]) <= 2.25)
            & (hit[..., 1] >= -0.05)
            & (hit[..., 1] <= 2.45)
            & (np.abs(hit[..., 2]) <= 2.25)
        )
        better = inside & (t < best_t)
        best_t[better] = t[better]
        face_id[better] = index
        if name in {"floor", "ceil"}:
            u = (hit[..., 0] + 2.2) / 4.4
            v = (hit[..., 2] + 2.2) / 4.4
        elif name in {"north", "south"}:
            u = (hit[..., 0] + 2.2) / 4.4
            v = hit[..., 1] / 2.4
        else:
            u = (hit[..., 2] + 2.2) / 4.4
            v = hit[..., 1] / 2.4
        uu[better] = u[better]
        vv[better] = v[better]
    out = np.zeros((size, size, 3), dtype=np.uint8)
    names = ("floor", "ceil", "north", "south", "east", "west")
    for index, name in enumerate(names, start=1):
        mask = face_id == index
        if not np.any(mask):
            continue
        tex = textures[name]
        px = np.clip((uu[mask] * (tex.shape[1] - 1)).astype(np.int32), 0, tex.shape[1] - 1)
        py = np.clip(((1.0 - vv[mask]) * (tex.shape[0] - 1)).astype(np.int32), 0, tex.shape[0] - 1)
        out[mask] = tex[py, px]
    return Image.fromarray(out, "RGB")


def main(out_dir: Path, frames: int = 72) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    textures = _wall_textures()
    for index in range(frames):
        yaw = 2.0 * math.pi * index / frames
        render_frame(textures, yaw).save(out_dir / f"frame_{index:04d}.jpg", quality=92)
    return out_dir


if __name__ == "__main__":
    import sys

    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("room_frames"))
