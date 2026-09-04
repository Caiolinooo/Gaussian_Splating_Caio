"""Adaptive rate, Laplacian blur, dedup, image validation — no ffmpeg."""

from __future__ import annotations

from pathlib import Path

import pytest

from ingest.adaptive import compute_adaptive_rate, format_fps
from ingest.config import ImageInfo, ImageIngestConfig
from ingest.errors import IngestError
from ingest.images import ingest_images, next_version_dir, validate_image_info
from ingest.quality import (
    FrameScore,
    compute_normalized_size,
    is_near_duplicate,
    laplacian_variance,
    perceptual_signature,
    select_frames,
    signature_distance,
)


def _flat(width: int = 16, height: int = 16, value: float = 128.0) -> list[list[float]]:
    return [[value for _ in range(width)] for _ in range(height)]


def _checker(width: int = 16, height: int = 16) -> list[list[float]]:
    return [[float((x + y) % 2) * 255.0 for x in range(width)] for y in range(height)]


def test_adaptive_rate_short_clip_extracts_all() -> None:
    rate = compute_adaptive_rate(10.0, 30.0, target_min=150, target_max=400)
    assert rate.strategy == "all"
    assert rate.source_frame_count == 300
    assert rate.expected_extract_count == 300
    assert rate.target_keep_count == 300
    assert rate.warning is None


def test_adaptive_rate_long_clip_downsamples_toward_400() -> None:
    rate = compute_adaptive_rate(60.0, 30.0, target_min=150, target_max=400, oversample=1.25)
    assert rate.strategy == "downsample"
    assert rate.target_keep_count == 400
    assert 400 <= rate.expected_extract_count <= 500
    assert rate.extract_fps == pytest.approx(rate.expected_extract_count / 60.0)


def test_adaptive_rate_very_short_warns() -> None:
    rate = compute_adaptive_rate(3.0, 30.0, target_min=150, target_max=400)
    assert rate.strategy == "sparse"
    assert rate.source_frame_count == 90
    assert rate.warning is not None
    assert "Poucos frames" in rate.warning


def test_adaptive_rate_rejects_bad_probe() -> None:
    with pytest.raises(IngestError) as exc:
        compute_adaptive_rate(0.0, 30.0)
    assert exc.value.code == "VIDEO_UNREADABLE"


def test_format_fps_stable() -> None:
    assert format_fps(30.0) == "30"
    assert format_fps(8.3333).startswith("8.33")


def test_laplacian_sharp_beats_blur() -> None:
    sharp = laplacian_variance(_checker())
    blur = laplacian_variance(_flat())
    assert sharp > blur
    assert blur == pytest.approx(0.0)


def test_signature_near_duplicate() -> None:
    left = perceptual_signature(_flat(value=100))
    right = perceptual_signature(_flat(value=102))
    far = perceptual_signature(_checker())
    assert is_near_duplicate(left, right, threshold=4.0)
    assert signature_distance(left, far) > 4.0
    assert not is_near_duplicate(left, far, threshold=4.0)


def test_select_frames_drops_blur_and_dups_then_caps() -> None:
    scores = [
        FrameScore(0, "a", 10.0, (1,) * 8),
        FrameScore(1, "b", 200.0, (2,) * 8),
        FrameScore(2, "c", 210.0, (2,) * 8),
        FrameScore(3, "d", 180.0, (10,) * 8),
        FrameScore(4, "e", 190.0, (14,) * 8),
    ]
    selection = select_frames(
        scores,
        blur_threshold=80.0,
        relaxed_blur_threshold=40.0,
        dedup_threshold=4.0,
        target_min=1,
        target_max=2,
    )
    assert "a" not in {item.path for item in selection.kept}
    assert len(selection.dropped_blur) == 1
    assert selection.dropped_dup
    assert len(selection.kept) <= 2


def test_select_frames_relaxes_blur_when_too_few() -> None:
    scores = [
        FrameScore(0, "a", 50.0, (1,)),
        FrameScore(1, "b", 55.0, (8,)),
    ]
    selection = select_frames(
        scores,
        blur_threshold=80.0,
        relaxed_blur_threshold=40.0,
        dedup_threshold=0.5,
        target_min=2,
        target_max=10,
    )
    assert selection.blur_threshold_used == 40.0
    assert len(selection.kept) == 2


def test_normalized_size_even_and_capped() -> None:
    assert compute_normalized_size(1920, 1080, max_edge=1600) == (1600, 900)
    assert compute_normalized_size(800, 600, max_edge=1600) == (800, 600)
    width, height = compute_normalized_size(1001, 501, max_edge=200)
    assert width % 2 == 0 and height % 2 == 0


def test_validate_image_rejects_format_and_size() -> None:
    cfg = ImageIngestConfig(min_width=640, min_height=480)
    with pytest.raises(IngestError) as bad_fmt:
        validate_image_info(
            ImageInfo(Path("x.gif"), 800, 600, "gif", ".gif"),
            cfg,
        )
    assert bad_fmt.value.code == "INVALID_FORMAT"
    with pytest.raises(IngestError) as tiny:
        validate_image_info(
            ImageInfo(Path("x.jpg"), 320, 240, "jpeg", ".jpg"),
            cfg,
        )
    assert tiny.value.code == "TOO_SMALL"
    ok = validate_image_info(ImageInfo(Path("x.jpg"), 1280, 720, "jpeg", ".jpg"), cfg)
    assert ok.width == 1280


def test_next_version_dir_increments(tmp_path: Path) -> None:
    first = next_version_dir(tmp_path)
    first.mkdir()
    second = next_version_dir(tmp_path)
    assert first.name == "v001"
    assert second.name == "v002"


def test_ingest_images_versioned_copy(tmp_path: Path) -> None:
    src = tmp_path / "sala.jpg"
    src.write_bytes(b"not-a-real-jpeg")

    def prober(path: Path) -> ImageInfo:
        return ImageInfo(path, 1280, 720, "jpeg", ".jpg")

    first = ingest_images(
        [src],
        tmp_path / "versions",
        ImageIngestConfig(),
        prober=prober,
    )
    second = ingest_images(
        [src],
        tmp_path / "versions",
        ImageIngestConfig(),
        prober=prober,
    )
    assert first.version == 1
    assert second.version == 2
    assert first.copied[0].is_file()
    assert (tmp_path / "versions" / "current.json").is_file()
