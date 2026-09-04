"""COLMAP log / images.txt parsing and quality-gate messages."""

from __future__ import annotations

import pytest

from sfm.errors import SfmError
from sfm.parse import (
    detect_sfm_failure,
    parse_colmap_log,
    parse_images_txt,
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


def test_summarize_raises_when_ratio_below_70_percent() -> None:
    with pytest.raises(SfmError) as exc:
        summarize_reconstruction(
            images_txt=IMAGES_TXT,
            log_text="",
            input_image_count=20,
            min_registered_ratio=0.70,
            min_registered_count=2,
        )
    assert exc.value.code == "FEW_REGISTERED"
    assert "Registradas: 2 de 20" in exc.value.user_message


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
