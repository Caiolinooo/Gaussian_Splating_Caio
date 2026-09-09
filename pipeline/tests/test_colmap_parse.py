"""COLMAP log / images.txt parsing and quality-gate messages."""

from __future__ import annotations

from pathlib import Path

import pytest

from sfm.config import VIDEO_MIN_REGISTERED_RATIO, ColmapConfig
from sfm.errors import SfmError
from sfm.parse import (
    detect_sfm_failure,
    parse_colmap_log,
    parse_images_txt,
    pick_largest_model,
    summarize_reconstruction,
)

IMAGES_TXT = """# Image list with two lines of data per image:
#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME
#   POINTS2D[] as (X, Y, POINT3D_ID)
1 0.1 0.2 0.3 0.4 0.0 1.0 2.0 1 frame_000001.jpg
100 200 1 110 210 2
2 0.2 0.1 0.0 0.9 -1.0 0.5 0.0 1 frame_000002.jpg
50 60 -1
"""


def test_parse_images_txt_two_lines_per_image() -> None:
    images = parse_images_txt(IMAGES_TXT)
    assert len(images) == 2
    assert images[0].image_id == 1
    assert images[0].name == "frame_000001.jpg"
    assert images[1].camera_id == 1
    assert images[1].name == "frame_000002.jpg"


def test_parse_colmap_log_registering_lines() -> None:
    log = (
        "I2026 feature_extractor\n"
        "Registering image #12\n"
        "Registering image #44\n"
        "Registered images: 80\n"
    )
    ids = parse_colmap_log(log)
    assert ids == (12, 44)


def test_few_matches_is_explicable() -> None:
    error = detect_sfm_failure("=> No good initial image pair found.")
    assert error is not None
    assert error.code == "FEW_MATCHES"
    assert "Poucas correspondências" in error.user_message
    assert "textura" in error.user_message


def _images_txt(count: int) -> str:
    lines = ["# Image list with two lines of data per image:"]
    for index in range(1, count + 1):
        lines.append(f"{index} 0.1 0.2 0.3 0.4 0.0 1.0 2.0 1 frame_{index:06d}.jpg")
        lines.append("100 200 1")
    return "\n".join(lines) + "\n"


def test_summarize_20_of_188_warns_but_passes() -> None:
    summary = summarize_reconstruction(
        images_txt=_images_txt(20),
        log_text="",
        input_image_count=188,
        min_registered_ratio=0.70,
        min_registered_count=20,
    )
    assert summary.registered_count == 20
    assert summary.ratio == pytest.approx(20 / 188)
    assert summary.warning is not None
    assert "20 de 188" in summary.warning
    assert "não é preciso filmar de novo" in summary.warning


def test_summarize_5_of_188_still_fails() -> None:
    with pytest.raises(SfmError) as exc:
        summarize_reconstruction(
            images_txt=_images_txt(5),
            log_text="",
            input_image_count=188,
            min_registered_ratio=0.70,
            min_registered_count=20,
        )
    assert exc.value.code == "FEW_REGISTERED"
    assert "Registradas: 5 de 188" in exc.value.user_message
    assert "mínimo 20 poses" in exc.value.user_message
    assert "Filme com" not in exc.value.user_message


def test_video_ratio_is_capped_below_70_percent() -> None:
    cfg = ColmapConfig(min_registered_ratio=0.70)
    assert cfg.effective_min_registered_ratio("video") == pytest.approx(VIDEO_MIN_REGISTERED_RATIO)
    assert cfg.effective_min_registered_ratio("images") == pytest.approx(0.70)


def test_pick_largest_model_prefers_more_cameras(tmp_path: Path) -> None:
    sparse = tmp_path / "sparse"
    junk = sparse / "0"
    gold = sparse / "3"
    junk.mkdir(parents=True)
    gold.mkdir(parents=True)
    (junk / "images.txt").write_text(_images_txt(5), encoding="utf-8")
    (junk / "points3D.txt").write_text("# one\n1 0 0 0 0 0 0 0\n", encoding="utf-8")
    (gold / "images.txt").write_text(_images_txt(90), encoding="utf-8")
    (gold / "points3D.txt").write_text("# many\n" + "1 0 0 0 0 0 0 0\n" * 20, encoding="utf-8")
    assert pick_largest_model(sparse) == gold


def test_summarize_ok_when_ratio_passes() -> None:
    summary = summarize_reconstruction(
        images_txt=IMAGES_TXT,
        log_text="Registering image #1\nRegistering image #2\n",
        input_image_count=2,
        min_registered_ratio=0.70,
        min_registered_count=2,
    )
    assert summary.registered_count == 2
    assert summary.ratio == pytest.approx(1.0)


def test_zero_registered_without_log_hint() -> None:
    with pytest.raises(SfmError) as exc:
        summarize_reconstruction(
            images_txt="",
            log_text="",
            input_image_count=40,
            min_registered_ratio=0.70,
            min_registered_count=20,
        )
    assert exc.value.code == "NO_RECONSTRUCTION"
