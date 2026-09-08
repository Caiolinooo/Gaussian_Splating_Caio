"""SfM runner maps a missing COLMAP binary to COLMAP_FAILED."""

from __future__ import annotations

from pathlib import Path

import pytest

from sfm.config import ColmapConfig, ColmapPaths
from sfm.errors import COLMAP_MISSING_USER, SfmError, colmap_missing
from sfm.runner import run_sfm


class _MissingBinary:
    def run(self, argv: object, **_kwargs: object) -> object:
        raise FileNotFoundError(2, "The system cannot find the file specified", argv[0])  # type: ignore[index]


def test_colmap_missing_factory() -> None:
    error = colmap_missing("colmap")
    assert error.code == "COLMAP_FAILED"
    assert "Setup" in error.user_message
    assert error.user_message == COLMAP_MISSING_USER


def test_run_sfm_missing_binary_is_colmap_failed(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "a.jpg").write_bytes(b"x")
    with pytest.raises(SfmError) as exc:
        run_sfm(
            ColmapConfig(),
            ColmapPaths(image_dir=images, work_dir=tmp_path / "colmap"),
            _MissingBinary(),
            source_kind="images",
        )
    assert exc.value.code == "COLMAP_FAILED"
    assert "Setup" in exc.value.user_message
