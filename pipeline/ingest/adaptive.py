"""Adaptive frame-rate selection targeting 150–400 frames."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ingest.errors import IngestError

Strategy = Literal["all", "downsample", "sparse"]


@dataclass(frozen=True)
class AdaptiveRate:
    source_fps: float
    duration_s: float
    source_frame_count: int
    extract_fps: float
    expected_extract_count: int
    target_keep_count: int
    strategy: Strategy
    warning: str | None = None


def format_fps(fps: float) -> str:
    """Stable fps token for ffmpeg ``-vf fps=``."""
    if fps <= 0:
        raise ValueError("fps must be positive")
    rounded = round(fps)
    if abs(fps - rounded) < 1e-6:
        return str(int(rounded))
    text = f"{fps:.4f}".rstrip("0").rstrip(".")
    return text


def compute_adaptive_rate(
    duration_s: float,
    source_fps: float,
    *,
    target_min: int = 150,
    target_max: int = 400,
    oversample: float = 1.25,
) -> AdaptiveRate:
    """Choose an extract fps so kept frames land in ``[target_min, target_max]``.

    Long clips are downsampled toward ``target_max`` with a small oversample
    so blur/dedup can discard leftovers. Short clips extract every frame and
    emit a user-facing warning when below ``target_min``.
    """
    if duration_s <= 0 or source_fps <= 0:
        raise IngestError(
            f"invalid probe duration={duration_s} fps={source_fps}",
            user_message="O vídeo não tem duração ou taxa de quadros válida.",
            code="VIDEO_UNREADABLE",
        )
    if target_min < 1 or target_max < target_min or oversample < 1.0:
        raise ValueError("invalid adaptive-rate bounds")

    source_count = max(1, int(round(duration_s * source_fps)))
    if source_count < target_min:
        return AdaptiveRate(
            source_fps=source_fps,
            duration_s=duration_s,
            source_frame_count=source_count,
            extract_fps=source_fps,
            expected_extract_count=source_count,
            target_keep_count=source_count,
            strategy="sparse",
            warning=(
                "Poucos frames no vídeo — grave mais tempo ou envie um "
                "conjunto maior de imagens."
            ),
        )
    if source_count <= target_max:
        return AdaptiveRate(
            source_fps=source_fps,
            duration_s=duration_s,
            source_frame_count=source_count,
            extract_fps=source_fps,
            expected_extract_count=source_count,
            target_keep_count=source_count,
            strategy="all",
        )

    extract_count = min(source_count, int(round(target_max * oversample)))
    extract_fps = extract_count / duration_s
    return AdaptiveRate(
        source_fps=source_fps,
        duration_s=duration_s,
        source_frame_count=source_count,
        extract_fps=extract_fps,
        expected_extract_count=extract_count,
        target_keep_count=target_max,
        strategy="downsample",
    )
