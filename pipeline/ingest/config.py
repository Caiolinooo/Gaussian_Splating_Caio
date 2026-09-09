"""Ingest configuration (video frames and still-image sets)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED_IMAGE_SUFFIXES: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".heic", ".heif", ".bmp"}
)
SUPPORTED_VIDEO_SUFFIXES: frozenset[str] = frozenset(
    {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
)


@dataclass(frozen=True)
class VideoIngestConfig:
    """Adaptive frame extraction + quality filters."""

    target_min_frames: int = 180
    target_max_frames: int = 220
    oversample: float = 1.15
    blur_threshold: float = 80.0
    relaxed_blur_threshold: float = 40.0
    # 8×8 mean signatures move slowly on a room walk; 4.0 treated every
    # consecutive frame as a dup (prod job: 183 sharp → 19 kept).
    dedup_threshold: float = 1.0
    relaxed_dedup_threshold: float = 0.5
    min_keep_frames: int = 8
    max_edge_px: int = 1600
    jpeg_quality: int = 2
    min_width: int = 640
    min_height: int = 480
    signature_size: int = 8

    def __post_init__(self) -> None:
        if self.target_min_frames < 1:
            raise ValueError("target_min_frames must be >= 1")
        if self.target_max_frames < self.target_min_frames:
            raise ValueError("target_max_frames must be >= target_min_frames")
        if self.oversample < 1.0:
            raise ValueError("oversample must be >= 1.0")
        if self.min_keep_frames < 1:
            raise ValueError("min_keep_frames must be >= 1")
        if self.max_edge_px < 64:
            raise ValueError("max_edge_px must be >= 64")


@dataclass(frozen=True)
class ImageIngestConfig:
    """Validation + versioned copy for a still-image set (skips ffmpeg)."""

    min_width: int = 640
    min_height: int = 480
    max_edge_px: int = 1280
    allowed_suffixes: frozenset[str] = field(default_factory=lambda: SUPPORTED_IMAGE_SUFFIXES)
    normalize_resolution: bool = True

    def __post_init__(self) -> None:
        if self.min_width < 1 or self.min_height < 1:
            raise ValueError("minimum dimensions must be >= 1")


@dataclass(frozen=True)
class ToolBins:
    """Resolved binary names/paths (Provisioner fills these on the worker)."""

    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"


@dataclass(frozen=True)
class VideoProbe:
    path: Path
    width: int
    height: int
    duration_s: float
    fps: float
    nb_frames: int | None = None


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    width: int
    height: int
    format: str
    suffix: str
