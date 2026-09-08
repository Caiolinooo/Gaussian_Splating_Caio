"""SfM runner: missing binary, GPU→CPU fallback, stale-state cleanup, log file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from sfm.config import ColmapConfig, ColmapPaths
from sfm.errors import COLMAP_MISSING_USER, SfmError, colmap_missing
from sfm.runner import run_sfm

IMAGES_TXT = """# Image list with two lines of data per image:
#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME
1 0.1 0.2 0.3 0.4 0.0 1.0 2.0 1 frame_000001.jpg
100 200 1 110 210 2
2 0.2 0.1 0.0 0.9 -1.0 0.5 0.0 1 frame_000002.jpg
50 60 -1
"""


@dataclass
class _FakeResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _is_gpu_invocation(argv: list[str]) -> bool:
    for flag in ("--SiftExtraction.use_gpu", "--SiftMatching.use_gpu"):
        if flag in argv and argv[argv.index(flag) + 1] == "1":
            return True
    return False


class _FakeColmap:
    """GPU-flagged steps fail (headless GL); CPU steps succeed and emit a model."""

    def __init__(self, fail_gpu: bool = True) -> None:
        self.calls: list[list[str]] = []
        self.fail_gpu = fail_gpu

    def run(self, argv: Any, **_kwargs: Any) -> _FakeResult:
        argv = list(argv)
        self.calls.append(argv)
        step = argv[1]
        if self.fail_gpu and _is_gpu_invocation(argv):
            return _FakeResult(1, stderr="OpenGL context unavailable (headless server)")
        if step == "mapper":
            out = Path(argv[argv.index("--output_path") + 1]) / "0"
            out.mkdir(parents=True, exist_ok=True)
            (out / "images.bin").write_bytes(b"bin")
        if step == "model_converter":
            out = Path(argv[argv.index("--output_path") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / "images.txt").write_text(IMAGES_TXT, encoding="utf-8")
        return _FakeResult(0, stdout=f"{step} ok")


class _AlwaysFail:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, argv: Any, **_kwargs: Any) -> _FakeResult:
        argv = list(argv)
        self.calls.append(argv)
        return _FakeResult(1, stderr="boom")


class _MissingBinary:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, argv: Any, **_kwargs: Any) -> Any:
        self.calls.append(list(argv))
        raise FileNotFoundError(2, "The system cannot find the file specified", argv[0])


def _images(tmp_path: Path) -> Path:
    images = tmp_path / "images"
    images.mkdir(exist_ok=True)
    (images / "frame_000001.jpg").write_bytes(b"x")
    (images / "frame_000002.jpg").write_bytes(b"x")
    return images


def _config(**overrides: Any) -> ColmapConfig:
    base: dict[str, Any] = {"min_registered_count": 2, "min_registered_ratio": 0.5}
    base.update(overrides)
    return ColmapConfig(**base)


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


def test_missing_binary_does_not_trigger_cpu_fallback(tmp_path: Path) -> None:
    runner = _MissingBinary()
    with pytest.raises(SfmError) as exc:
        run_sfm(
            _config(),
            ColmapPaths(image_dir=_images(tmp_path), work_dir=tmp_path / "colmap"),
            runner,
            source_kind="images",
        )
    assert exc.value.code == "COLMAP_FAILED"
    assert len(runner.calls) == 1


def test_gpu_failure_falls_back_to_cpu(tmp_path: Path) -> None:
    work = tmp_path / "colmap"
    runner = _FakeColmap(fail_gpu=True)
    result = run_sfm(
        _config(),
        ColmapPaths(image_dir=_images(tmp_path), work_dir=work),
        runner,
        source_kind="images",
    )
    assert result.used_gpu is False
    assert result.summary.registered_count == 2
    assert any(_is_gpu_invocation(call) for call in runner.calls)
    assert any(
        "--SiftExtraction.use_gpu" in call and call[call.index("--SiftExtraction.use_gpu") + 1] == "0"
        for call in runner.calls
    )
    log = (work / "colmap.log").read_text(encoding="utf-8")
    assert "OpenGL context unavailable" in log
    assert "use_gpu=0" in log
    assert result.log_path == work / "colmap.log"


def test_gpu_success_skips_cpu_fallback(tmp_path: Path) -> None:
    runner = _FakeColmap(fail_gpu=False)
    result = run_sfm(
        _config(),
        ColmapPaths(image_dir=_images(tmp_path), work_dir=tmp_path / "colmap"),
        runner,
        source_kind="images",
    )
    assert result.used_gpu is True
    assert all(_is_gpu_invocation(call) or call[1] in {"mapper", "model_converter"} for call in runner.calls)


def test_cpu_failure_does_not_retry(tmp_path: Path) -> None:
    runner = _AlwaysFail()
    with pytest.raises(SfmError) as exc:
        run_sfm(
            _config(use_gpu=False),
            ColmapPaths(image_dir=_images(tmp_path), work_dir=tmp_path / "colmap"),
            runner,
            source_kind="images",
        )
    assert exc.value.code == "COLMAP_FAILED"
    assert "boom" in str(exc.value)
    assert len(runner.calls) == 1


def test_mapper_failure_does_not_trigger_cpu_fallback(tmp_path: Path) -> None:
    class _MapperFail:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def run(self, argv: Any, **_kwargs: Any) -> _FakeResult:
            argv = list(argv)
            self.calls.append(argv)
            if argv[1] == "mapper":
                return _FakeResult(1, stderr="mapper exploded")
            return _FakeResult(0, stdout="ok")

    runner = _MapperFail()
    with pytest.raises(SfmError) as exc:
        run_sfm(
            _config(),
            ColmapPaths(image_dir=_images(tmp_path), work_dir=tmp_path / "colmap"),
            runner,
            source_kind="images",
        )
    assert exc.value.code == "COLMAP_FAILED"
    assert "mapper exploded" in str(exc.value)
    assert [call[1] for call in runner.calls] == ["feature_extractor", "exhaustive_matcher", "mapper"]


def test_stale_state_is_cleaned_before_run(tmp_path: Path) -> None:
    work = tmp_path / "colmap"
    stale_model = work / "sparse" / "0"
    stale_model.mkdir(parents=True)
    (stale_model / "stale.txt").write_text("junk", encoding="utf-8")
    (work / "database.db").write_bytes(b"corrupt")
    (work / "database.db-wal").write_bytes(b"x")
    (work / "database.db-shm").write_bytes(b"x")

    runner = _FakeColmap(fail_gpu=False)
    result = run_sfm(
        _config(use_gpu=False),
        ColmapPaths(image_dir=_images(tmp_path), work_dir=work),
        runner,
        source_kind="images",
    )
    assert result.summary.registered_count == 2
    assert not (stale_model / "stale.txt").exists()
    assert not (work / "database.db-wal").exists()
    assert not (work / "database.db-shm").exists()


def test_log_file_is_written_even_on_failure(tmp_path: Path) -> None:
    work = tmp_path / "colmap"
    runner = _AlwaysFail()
    with pytest.raises(SfmError):
        run_sfm(
            _config(use_gpu=False),
            ColmapPaths(image_dir=_images(tmp_path), work_dir=work),
            runner,
            source_kind="images",
        )
    log = (work / "colmap.log").read_text(encoding="utf-8")
    assert "feature_extractor" in log
    assert "boom" in log
