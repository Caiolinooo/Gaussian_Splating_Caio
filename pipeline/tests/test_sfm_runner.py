"""SfM runner: missing binary, CLI dialect probe, GPU→CPU fallback, stale-state cleanup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from sfm.config import ColmapConfig, ColmapPaths
from sfm.errors import COLMAP_MISSING_USER, SfmError, colmap_missing
from sfm.parse import parse_images_txt
from sfm.runner import run_sfm

IMAGES_TXT = """# Image list with two lines of data per image:
#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME
1 0.1 0.2 0.3 0.4 0.0 1.0 2.0 1 frame_000001.jpg
100 200 1 110 210 2
2 0.2 0.1 0.0 0.9 -1.0 0.5 0.0 1 frame_000002.jpg
50 60 -1
"""

LEGACY_HELP = "--SiftExtraction.use_gpu arg (=1)\n--SiftMatching.use_gpu arg (=1)\n"
V4_HELP = "--FeatureExtraction.use_gpu arg (=1)\n--FeatureMatching.use_gpu arg (=1)\n"


@dataclass
class _FakeResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _is_gpu_invocation(argv: list[str]) -> bool:
    gpu_flags = (
        "--SiftExtraction.use_gpu",
        "--SiftMatching.use_gpu",
        "--FeatureExtraction.use_gpu",
        "--FeatureMatching.use_gpu",
    )
    for flag in gpu_flags:
        if flag in argv and argv[argv.index(flag) + 1] == "1":
            return True
    return False


def _graph_calls(calls: list[list[str]]) -> list[list[str]]:
    """Sem as sondas de dialeto (`-h`)."""
    return [call for call in calls if "-h" not in call]


class _FakeColmap:
    """GPU-flagged steps fail (headless GL); CPU steps succeed and emit a model."""

    def __init__(self, fail_gpu: bool = True, help_text: str = LEGACY_HELP) -> None:
        self.calls: list[list[str]] = []
        self.fail_gpu = fail_gpu
        self.help_text = help_text

    def run(self, argv: Any, **_kwargs: Any) -> _FakeResult:
        argv = list(argv)
        self.calls.append(argv)
        if "-h" in argv:
            return _FakeResult(0, stdout=self.help_text)
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
    graph = _graph_calls(runner.calls)
    assert any(_is_gpu_invocation(call) for call in graph)
    assert any(
        "--SiftExtraction.use_gpu" in call and call[call.index("--SiftExtraction.use_gpu") + 1] == "0"
        for call in graph
    )
    log = (work / "colmap.log").read_text(encoding="utf-8")
    assert "OpenGL context unavailable" in log
    assert "use_gpu=0" in log
    assert result.log_path == work / "colmap.log"


def test_v4_dialect_uses_feature_extraction_flags(tmp_path: Path) -> None:
    work = tmp_path / "colmap"
    runner = _FakeColmap(fail_gpu=True, help_text=V4_HELP)
    result = run_sfm(
        _config(),
        ColmapPaths(image_dir=_images(tmp_path), work_dir=work),
        runner,
        source_kind="images",
    )
    assert result.used_gpu is False
    graph = _graph_calls(runner.calls)
    assert any(
        "--FeatureExtraction.use_gpu" in call and call[call.index("--FeatureExtraction.use_gpu") + 1] == "0"
        for call in graph
    )
    assert all("--SiftExtraction.use_gpu" not in call for call in graph)
    assert all("--SiftMatching.use_gpu" not in call for call in graph)


def test_unknown_dialect_omits_gpu_flags(tmp_path: Path) -> None:
    runner = _FakeColmap(fail_gpu=False, help_text="--database_path arg\n")
    result = run_sfm(
        _config(use_gpu=False),
        ColmapPaths(image_dir=_images(tmp_path), work_dir=tmp_path / "colmap"),
        runner,
        source_kind="images",
    )
    assert result.summary.registered_count == 2
    graph = _graph_calls(runner.calls)
    assert all("use_gpu" not in " ".join(call) for call in graph)


def test_gpu_success_skips_cpu_fallback(tmp_path: Path) -> None:
    runner = _FakeColmap(fail_gpu=False)
    result = run_sfm(
        _config(),
        ColmapPaths(image_dir=_images(tmp_path), work_dir=tmp_path / "colmap"),
        runner,
        source_kind="images",
    )
    assert result.used_gpu is True
    graph = _graph_calls(runner.calls)
    assert all(_is_gpu_invocation(call) or call[1] in {"mapper", "model_converter"} for call in graph)


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
    assert len(_graph_calls(runner.calls)) == 1


def test_mapper_failure_does_not_trigger_cpu_fallback(tmp_path: Path) -> None:
    class _MapperFail:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def run(self, argv: Any, **_kwargs: Any) -> _FakeResult:
            argv = list(argv)
            self.calls.append(argv)
            if "-h" in argv:
                return _FakeResult(0, stdout=LEGACY_HELP)
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
    assert [call[1] for call in _graph_calls(runner.calls)] == [
        "feature_extractor",
        "exhaustive_matcher",
        "mapper",
    ]


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


_ONE_IMAGE_TXT = "# one image\n1 0.1 0.2 0.3 0.4 0.0 1.0 2.0 1 frame_000001.jpg\n100 200 1\n"


class _GateFailUntilRescue:
    """Abaixo do gate de qualidade até a extração rodar com SIFT de resgate."""

    def __init__(self, fail_gpu: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.fail_gpu = fail_gpu
        self.rescued = False

    def run(self, argv: Any, **_kwargs: Any) -> _FakeResult:
        argv = list(argv)
        self.calls.append(argv)
        if "-h" in argv:
            return _FakeResult(0, stdout=LEGACY_HELP)
        if self.fail_gpu and _is_gpu_invocation(argv):
            return _FakeResult(1, stderr="OpenGL context unavailable")
        step = argv[1]
        if step == "feature_extractor" and "--SiftExtraction.peak_threshold" in argv:
            self.rescued = True
        if step == "mapper":
            out = Path(argv[argv.index("--output_path") + 1]) / "0"
            out.mkdir(parents=True, exist_ok=True)
            (out / "images.bin").write_bytes(b"bin")
        if step == "model_converter":
            out = Path(argv[argv.index("--output_path") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / "images.txt").write_text(
                IMAGES_TXT if self.rescued else _ONE_IMAGE_TXT, encoding="utf-8"
            )
        return _FakeResult(0, stdout=f"{step} ok")


def test_few_registered_triggers_rescue_with_relaxed_sift(tmp_path: Path) -> None:
    work = tmp_path / "colmap"
    runner = _GateFailUntilRescue()
    result = run_sfm(
        _config(use_gpu=False),
        ColmapPaths(image_dir=_images(tmp_path), work_dir=work),
        runner,
        source_kind="images",
    )
    assert result.summary.registered_count == 2
    graph = _graph_calls(runner.calls)
    extractor_calls = [call for call in graph if call[1] == "feature_extractor"]
    assert len(extractor_calls) == 2
    rescue = extractor_calls[1]
    assert rescue[rescue.index("--SiftExtraction.peak_threshold") + 1] == "0.004"
    assert rescue[rescue.index("--SiftExtraction.edge_threshold") + 1] == "15"
    assert rescue[rescue.index("--SiftExtraction.max_num_features") + 1] == "16384"
    log = (work / "colmap.log").read_text(encoding="utf-8")
    assert "rescue attempt with relaxed SIFT" in log


def test_rescue_exhausted_raises_few_registered(tmp_path: Path) -> None:
    runner = _GateFailUntilRescue()
    runner.rescued = False

    class _NeverRescue(_GateFailUntilRescue):
        def run(self, argv: Any, **kwargs: Any) -> _FakeResult:
            result = super().run(argv, **kwargs)
            self.rescued = False  # resgate nunca melhora o modelo
            return result

    runner2 = _NeverRescue()
    with pytest.raises(SfmError) as exc:
        run_sfm(
            _config(use_gpu=False),
            ColmapPaths(image_dir=_images(tmp_path), work_dir=tmp_path / "colmap"),
            runner2,
            source_kind="images",
        )
    assert exc.value.code == "FEW_REGISTERED"
    extractors = [call for call in _graph_calls(runner2.calls) if call[1] == "feature_extractor"]
    assert len(extractors) == 3  # original + resgate SIFT + PINHOLE/overlap
    assert extractors[2][extractors[2].index("--ImageReader.camera_model") + 1] == "PINHOLE"


def test_gpu_fallback_then_rescue_keeps_cpu_mode(tmp_path: Path) -> None:
    runner = _GateFailUntilRescue(fail_gpu=True)
    result = run_sfm(
        _config(),
        ColmapPaths(image_dir=_images(tmp_path), work_dir=tmp_path / "colmap"),
        runner,
        source_kind="images",
    )
    assert result.used_gpu is False
    assert result.summary.registered_count == 2
    graph = _graph_calls(runner.calls)
    rescue_extractors = [
        call for call in graph if call[1] == "feature_extractor" and "--SiftExtraction.peak_threshold" in call
    ]
    assert len(rescue_extractors) == 1
    assert rescue_extractors[0][rescue_extractors[0].index("--SiftExtraction.use_gpu") + 1] == "0"


def _images_txt(count: int) -> str:
    lines = ["# Image list with two lines of data per image:"]
    for index in range(1, count + 1):
        lines.append(f"{index} 0.1 0.2 0.3 0.4 0.0 1.0 2.0 1 frame_{index:06d}.jpg")
        lines.append("100 200 1")
    return "\n".join(lines) + "\n"


class _FragmentedColmap:
    """Mapper writes a junk sparse/0 and a larger sparse/3 (job 0284bca6)."""

    def __init__(self, junk: int = 5, gold: int = 20) -> None:
        self.calls: list[list[str]] = []
        self.junk = junk
        self.gold = gold

    def run(self, argv: Any, **_kwargs: Any) -> _FakeResult:
        argv = list(argv)
        self.calls.append(argv)
        if "-h" in argv:
            return _FakeResult(0, stdout=LEGACY_HELP)
        step = argv[1]
        if step == "mapper":
            sparse = Path(argv[argv.index("--output_path") + 1])
            for name, count in (("0", self.junk), ("3", self.gold)):
                model = sparse / name
                model.mkdir(parents=True, exist_ok=True)
                (model / "images.bin").write_bytes(b"bin")
                (model / "n_images").write_text(str(count), encoding="utf-8")
        if step == "model_converter":
            out = Path(argv[argv.index("--output_path") + 1])
            out.mkdir(parents=True, exist_ok=True)
            marker = out / "n_images"
            count = int(marker.read_text(encoding="utf-8")) if marker.is_file() else 2
            (out / "images.txt").write_text(_images_txt(count), encoding="utf-8")
        return _FakeResult(0, stdout=f"{step} ok")


def test_run_sfm_promotes_largest_sparse_model(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    for index in range(1, 189):
        (images / f"frame_{index:06d}.jpg").write_bytes(b"x")
    work = tmp_path / "colmap"
    result = run_sfm(
        _config(use_gpu=False, min_registered_count=20, min_registered_ratio=0.70),
        ColmapPaths(image_dir=images, work_dir=work),
        _FragmentedColmap(junk=5, gold=20),
        source_kind="video",
    )
    assert result.summary.registered_count == 20
    assert result.selected_sparse == "3"
    assert result.summary.warning is not None
    assert "20 de 188" in result.summary.warning
    promoted = parse_images_txt((work / "sparse" / "0" / "images.txt").read_text(encoding="utf-8"))
    assert len(promoted) == 20
    log = (work / "colmap.log").read_text(encoding="utf-8")
    assert "selected sparse/3" in log


def test_run_sfm_five_cameras_still_fail_after_rescue(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    for index in range(1, 189):
        (images / f"frame_{index:06d}.jpg").write_bytes(b"x")
    runner = _FragmentedColmap(junk=5, gold=5)
    with pytest.raises(SfmError) as exc:
        run_sfm(
            _config(use_gpu=False, min_registered_count=20, min_registered_ratio=0.70),
            ColmapPaths(image_dir=images, work_dir=tmp_path / "colmap"),
            runner,
            source_kind="video",
        )
    assert exc.value.code == "FEW_REGISTERED"
    assert "5 de 188" in exc.value.user_message
    extractors = [call for call in _graph_calls(runner.calls) if call[1] == "feature_extractor"]
    assert len(extractors) == 3
