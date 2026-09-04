"""Thumbnail source selection and size math (stdlib)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ThumbnailPlan:
    source: Path
    dest: Path
    width: int
    height: int


def compute_thumbnail_size(
    width: int,
    height: int,
    *,
    max_edge: int = 512,
) -> tuple[int, int]:
    if width < 1 or height < 1:
        raise ValueError("dimensions must be positive")
    scale = min(1.0, max_edge / float(max(width, height)))
    return max(1, int(width * scale)), max(1, int(height * scale))


def pick_thumbnail_source(
    *,
    render_dir: Path | None,
    frames_dir: Path | None,
    preferred_name: str = "preview",
) -> Path | None:
    """Prefer a gsplat val render; fall back to the first kept frame."""
    if render_dir is not None and render_dir.is_dir():
        renders = sorted(render_dir.glob("val_step*.png"))
        if renders:
            return renders[-1]
        any_png = sorted(render_dir.glob("*.png"))
        if any_png:
            return any_png[0]
    if frames_dir is not None and frames_dir.is_dir():
        frames = sorted(frames_dir.glob("*.jpg")) + sorted(frames_dir.glob("*.png"))
        if frames:
            return frames[0]
    _ = preferred_name
    return None
