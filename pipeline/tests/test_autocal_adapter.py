"""PipelineAutocal never fails the job; ColmapDepthProvider reads sparse SfM."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pydantic")

from jobs.autocal import AutocalContext
from jobs.autocal_adapter import ColmapDepthProvider, PipelineAutocal
from jobs.handlers import handle_autocal
from jobs.models import JobSpec, new_job_record
from jobs.states import SourceKind


def _context(tmp_path: Path, *, height: float = 1.75) -> AutocalContext:
    frames = tmp_path / "frames"
    frames.mkdir()
    (frames / "0001.jpg").write_bytes(b"not-a-real-jpeg")
    return AutocalContext(
        job_id="job-adapter",
        frames_dir=str(frames),
        user_height_m=height,
        registered_names=("0001.jpg",),
    )


def _write_colmap_model(model: Path) -> None:
    model.mkdir(parents=True)
    (model / "cameras.txt").write_text(
        "# CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n1 PINHOLE 100 100 50 50 50 50\n",
        encoding="utf-8",
    )
    (model / "images.txt").write_text(
        "# IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n"
        "1 1 0 0 0 0 0 2 1 frame.jpg\n"
        "50 50 1\n",
        encoding="utf-8",
    )
    (model / "points3D.txt").write_text(
        "# POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[]\n1 0 0 4 0 0 0 0\n",
        encoding="utf-8",
    )


def test_colmap_depth_provider_empty_is_none() -> None:
    provider = ColmapDepthProvider()
    assert provider.sample_depth("f", 0.5, 0.5, image_size=(1920, 1080)) is None
    assert (
        provider.person_height_scene_units("f", (0.5, 0.1), (0.5, 0.9), (1920, 1080)) is None
    )


def test_colmap_depth_provider_samples_sparse_z(tmp_path: Path) -> None:
    model = tmp_path / "sparse"
    _write_colmap_model(model)
    provider = ColmapDepthProvider(model)
    sample = provider.sample_depth("frame.jpg", 0.5, 0.5, image_size=(100, 100))
    assert sample is not None
    assert sample.focal_length_y_px == 50
    assert sample.depth_scene_units == pytest.approx(6.0)
    assert sample.is_heuristic is False
    height = provider.person_height_scene_units("frame.jpg", (0.5, 0.1), (0.5, 0.9), (100, 100))
    assert height == pytest.approx(80 * 6.0 / 50)


def test_pipeline_autocal_never_raises(tmp_path: Path) -> None:
    result = PipelineAutocal().run(_context(tmp_path))
    assert result.source in {"auto-height", "manual", "none"}
    assert 0.0 <= result.confidence <= 1.0
    assert result.frames_used >= 0
    assert isinstance(result.message, str)
    assert result.scene_calibration.get("source") in {"auto-height", "manual", "none"}


def test_pipeline_autocal_fallback_on_invalid_height(tmp_path: Path) -> None:
    result = PipelineAutocal().run(_context(tmp_path, height=0.0))
    assert result.confidence == 0.0
    assert result.source in {"auto-height", "none"}


def test_handle_autocal_writes_calibration_json(tmp_path: Path) -> None:
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"fake")
    record = new_job_record(
        JobSpec(
            user_id="user-a",
            source_kind=SourceKind.VIDEO,
            source_paths=(src,),
            user_height_m=1.75,
            work_root=tmp_path / "work",
        )
    )
    frames = record.work_path / "frames" / "kept"
    frames.mkdir(parents=True)
    (frames / "frame.jpg").write_bytes(b"x")
    record.stages["extracting"].artifacts["frames_dir"] = str(frames)

    outcome = handle_autocal(record, lambda *_args: None, PipelineAutocal())
    calib = Path(outcome.artifacts["calibration"])
    assert calib.is_file()
    text = calib.read_text(encoding="utf-8")
    assert "scaleFactor" in text
    assert "source" in text
