"""Blur (Laplacian variance), near-duplicate detection, resolution normalize.

All algorithms are stdlib-only so unit tests do not need numpy/OpenCV.
Pixels are row-major grayscale sequences with values in ``[0, 255]``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

Gray = Sequence[Sequence[float]]


@dataclass(frozen=True)
class FrameScore:
    index: int
    path: str
    sharpness: float
    signature: tuple[int, ...]


@dataclass(frozen=True)
class FrameSelection:
    kept: tuple[FrameScore, ...]
    dropped_blur: tuple[FrameScore, ...]
    dropped_dup: tuple[FrameScore, ...]
    dropped_overflow: tuple[FrameScore, ...]
    blur_threshold_used: float
    warning: str | None = None


def laplacian_variance(pixels: Gray) -> float:
    """Variance of a 4-neighbour Laplacian — higher means sharper."""
    height = len(pixels)
    if height < 3:
        return 0.0
    width = len(pixels[0])
    if width < 3:
        return 0.0

    values: list[float] = []
    append = values.append
    for y in range(1, height - 1):
        row_up = pixels[y - 1]
        row = pixels[y]
        row_down = pixels[y + 1]
        for x in range(1, width - 1):
            append(
                float(row_up[x])
                + float(row_down[x])
                + float(row[x - 1])
                + float(row[x + 1])
                - 4.0 * float(row[x])
            )
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def perceptual_signature(pixels: Gray, size: int = 8) -> tuple[int, ...]:
    """Box-downsampled means (``size×size`` values in ``0..255``)."""
    if size < 1:
        raise ValueError("signature size must be >= 1")
    height = len(pixels)
    width = len(pixels[0]) if height else 0
    if height == 0 or width == 0:
        return tuple(0 for _ in range(size * size))

    signature: list[int] = []
    for gy in range(size):
        y0 = int(gy * height / size)
        y1 = max(y0 + 1, int((gy + 1) * height / size))
        for gx in range(size):
            x0 = int(gx * width / size)
            x1 = max(x0 + 1, int((gx + 1) * width / size))
            total = 0.0
            count = 0
            for y in range(y0, y1):
                row = pixels[y]
                for x in range(x0, x1):
                    total += float(row[x])
                    count += 1
            mean = total / max(count, 1)
            signature.append(int(min(255, max(0, round(mean)))))
    return tuple(signature)


def signature_distance(left: Sequence[int], right: Sequence[int]) -> float:
    """Mean absolute difference between two signatures."""
    if len(left) != len(right):
        raise ValueError("signature length mismatch")
    if not left:
        return 0.0
    return sum(abs(int(a) - int(b)) for a, b in zip(left, right, strict=True)) / len(left)


def is_near_duplicate(
    left: Sequence[int],
    right: Sequence[int],
    *,
    threshold: float,
) -> bool:
    return signature_distance(left, right) < threshold


def compute_normalized_size(
    width: int,
    height: int,
    *,
    max_edge: int = 1600,
) -> tuple[int, int]:
    """Fit inside ``max_edge`` preserving aspect; both sides even (codec/COLMAP)."""
    if width < 1 or height < 1:
        raise ValueError("dimensions must be positive")
    if max_edge < 2:
        raise ValueError("max_edge must be >= 2")
    scale = min(1.0, max_edge / float(max(width, height)))
    new_w = int(width * scale)
    new_h = int(height * scale)
    new_w -= new_w % 2
    new_h -= new_h % 2
    return max(new_w, 2), max(new_h, 2)


def _evenly_pick(items: Sequence[FrameScore], count: int) -> list[FrameScore]:
    if count >= len(items):
        return list(items)
    if count <= 1:
        return [items[0]] if items else []
    last = len(items) - 1
    chosen: list[FrameScore] = []
    seen: set[int] = set()
    for slot in range(count):
        index = int(round(slot * last / (count - 1)))
        if index in seen:
            index = next((i for i in range(len(items)) if i not in seen), index)
        seen.add(index)
        chosen.append(items[index])
    return chosen


def select_frames(
    scores: Sequence[FrameScore],
    *,
    blur_threshold: float,
    relaxed_blur_threshold: float,
    dedup_threshold: float,
    target_min: int,
    target_max: int,
) -> FrameSelection:
    """Drop blurry and near-duplicate frames, then cap at ``target_max``."""
    if not scores:
        return FrameSelection(
            kept=(),
            dropped_blur=(),
            dropped_dup=(),
            dropped_overflow=(),
            blur_threshold_used=blur_threshold,
            warning="Nenhum frame disponível após a extração.",
        )

    ordered = tuple(scores)
    threshold = blur_threshold
    sharp = [item for item in ordered if item.sharpness >= threshold]
    dropped_blur = [item for item in ordered if item.sharpness < threshold]
    if len(sharp) < target_min and relaxed_blur_threshold < threshold:
        threshold = relaxed_blur_threshold
        sharp = [item for item in ordered if item.sharpness >= threshold]
        dropped_blur = [item for item in ordered if item.sharpness < threshold]

    kept: list[FrameScore] = []
    dropped_dup: list[FrameScore] = []
    last_kept: FrameScore | None = None
    for item in sharp:
        if last_kept is not None and is_near_duplicate(
            last_kept.signature,
            item.signature,
            threshold=dedup_threshold,
        ):
            if item.sharpness > last_kept.sharpness:
                dropped_dup.append(last_kept)
                kept[-1] = item
                last_kept = item
            else:
                dropped_dup.append(item)
            continue
        kept.append(item)
        last_kept = item

    dropped_overflow: list[FrameScore] = []
    if len(kept) > target_max:
        picked = _evenly_pick(kept, target_max)
        picked_ids = {id(item) for item in picked}
        dropped_overflow = [item for item in kept if id(item) not in picked_ids]
        kept = picked

    warning: str | None = None
    if len(kept) < target_min:
        warning = (
            f"Só restaram {len(kept)} frames nítidos (alvo mínimo {target_min}). "
            "Grave com mais textura, luz uniforme e menos movimento brusco."
        )

    return FrameSelection(
        kept=tuple(kept),
        dropped_blur=tuple(dropped_blur),
        dropped_dup=tuple(dropped_dup),
        dropped_overflow=tuple(dropped_overflow),
        blur_threshold_used=threshold,
        warning=warning,
    )
