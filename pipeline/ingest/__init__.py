"""Ingest: video (ffmpeg + quality filters) or still-image sets (no ffmpeg)."""

from ingest.adaptive import AdaptiveRate, compute_adaptive_rate, format_fps
from ingest.config import (
    ImageInfo,
    ImageIngestConfig,
    ToolBins,
    VideoIngestConfig,
    VideoProbe,
)
from ingest.errors import IngestError
from ingest.images import ImageIngestResult, ingest_images, next_version_dir, validate_image_info
from ingest.probe import build_ffprobe_command, parse_ffprobe_json
from ingest.quality import (
    FrameScore,
    FrameSelection,
    compute_normalized_size,
    is_near_duplicate,
    laplacian_variance,
    perceptual_signature,
    select_frames,
    signature_distance,
)
from ingest.video import (
    VideoIngestResult,
    build_ffmpeg_extract_command,
    ingest_video,
    score_frame,
)

__all__ = [
    "AdaptiveRate",
    "FrameScore",
    "FrameSelection",
    "ImageIngestConfig",
    "ImageIngestResult",
    "ImageInfo",
    "IngestError",
    "ToolBins",
    "VideoIngestConfig",
    "VideoIngestResult",
    "VideoProbe",
    "build_ffmpeg_extract_command",
    "build_ffprobe_command",
    "compute_adaptive_rate",
    "compute_normalized_size",
    "format_fps",
    "ingest_images",
    "ingest_video",
    "is_near_duplicate",
    "laplacian_variance",
    "next_version_dir",
    "parse_ffprobe_json",
    "perceptual_signature",
    "score_frame",
    "select_frames",
    "signature_distance",
    "validate_image_info",
]
