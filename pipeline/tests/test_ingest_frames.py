"""Adaptive rate, Laplacian blur, dedup, image validation — no ffmpeg."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ingest.adaptive import compute_adaptive_rate, format_fps
from ingest.config import ImageInfo, ImageIngestConfig, ToolBins, VideoIngestConfig
from ingest.errors import IngestError
from ingest.images import ingest_images, next_version_dir, validate_image_info
from ingest.quality import (
    FrameScore,
    compute_keep_floor,
    compute_normalized_size,
    compute_quality_target,
    is_near_duplicate,
    laplacian_variance,
    perceptual_signature,
    require_kept_frames,
    select_frames,
    signature_distance,
)
from ingest.video import ingest_video


def _flat(width: int = 16, height: int = 16, value: float = 128.0) -> list[list[float]]:
    return [[value for _ in range(width)] for _ in range(height)]


def _checker(width: int = 16, height: int = 16) -> list[list[float]]:
    return [[float((x + y) % 2) * 255.0 for x in range(width)] for y in range(height)]


def test_adaptive_rate_at_target_min_extracts_all() -> None:
    rate = compute_adaptive_rate(5.0, 30.0, target_min=150, target_max=180)
    assert rate.strategy == "all"
    assert rate.source_frame_count == 150
    assert rate.expected_extract_count == 150
    assert rate.target_keep_count == 150
    assert rate.warning is None


def test_adaptive_rate_dense_short_clip_caps_at_target_max() -> None:
    """10s @ 30fps = 300 frames — não extrair tudo (job 0284bca6)."""
    rate = compute_adaptive_rate(10.0, 30.0, target_min=150, target_max=180, oversample=1.15)
    assert rate.strategy == "downsample"
    assert rate.source_frame_count == 300
    assert rate.target_keep_count == 180
    assert rate.expected_extract_count == int(round(180 * 1.15))


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


def test_keep_floor_is_unusable_not_extract_target() -> None:
    assert compute_keep_floor(301, source_kind="video") == 8
    assert compute_keep_floor(40, source_kind="video") == 8
    assert compute_keep_floor(12, source_kind="gif") == 1
    assert compute_quality_target(301) == 120
    assert compute_quality_target(20) == 20


def test_nineteen_kept_of_min_150_now_proceeds() -> None:
    """Production job 0284bca6: 19 kept after filter used to die at min 150."""
    floor = require_kept_frames(19, 301, source_kind="video")
    assert floor == 8
    with pytest.raises(IngestError) as exc:
        require_kept_frames(5, 301, source_kind="video")
    assert exc.value.code == "TOO_FEW_FRAMES"
    assert "mínimo 8" in exc.value.user_message
    assert "Grave com mais tempo" not in exc.value.user_message
    require_kept_frames(3, 12, source_kind="gif")


def test_select_frames_relaxes_dedup_when_too_few() -> None:
    """8×8 signatures with MAD ~1–2 used to all count as dups at threshold 4."""
    scores = [
        FrameScore(index, f"f{index}", 80.0, (index % 3,) * 8)
        for index in range(12)
    ]
    tight = select_frames(
        scores,
        blur_threshold=40.0,
        relaxed_blur_threshold=20.0,
        dedup_threshold=4.0,
        relaxed_dedup_threshold=4.0,
        target_min=8,
        target_max=400,
    )
    assert len(tight.kept) == 1
    relaxed = select_frames(
        scores,
        blur_threshold=40.0,
        relaxed_blur_threshold=20.0,
        dedup_threshold=4.0,
        relaxed_dedup_threshold=0.5,
        target_min=8,
        target_max=400,
    )
    assert len(relaxed.kept) >= 8
    assert relaxed.dedup_threshold_used == 0.5


def test_ingest_video_nineteen_kept_writes_frames(tmp_path: Path) -> None:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"fake-mp4")

    class Runner:
        def run(self, argv, *, cwd=None, env=None, timeout_s=None):
            del cwd, env, timeout_s
            if "ffprobe" in str(argv[0]):
                payload = {
                    "streams": [
                        {
                            "width": 720,
                            "height": 1280,
                            "duration": "10.9",
                            "r_frame_rate": "30/1",
                            "nb_frames": "296",
                        }
                    ],
                    "format": {"duration": "10.9"},
                }
                return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
            raw_dir = Path(argv[-1]).parent
            for index in range(1, 41):
                (raw_dir / f"frame_{index:06d}.jpg").write_bytes(b"x")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

    def score_fn(path: Path, index: int) -> FrameScore:
        if index < 19:
            return FrameScore(index, str(path), 200.0, (index * 20,) * 8)
        return FrameScore(index, str(path), 5.0, (0,) * 8)

    result = ingest_video(
        src,
        tmp_path / "out",
        VideoIngestConfig(),
        ToolBins(),
        Runner(),
        score_fn=score_fn,
        source_kind="video",
    )
    assert len(result.kept_paths) == 19
    assert (tmp_path / "out" / "manifest.json").is_file()


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
