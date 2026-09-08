"""Unified SceneIO: detect, PLY ingest, export package — no parallel pipelines."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from export.config import ExportConfig
from ingest.config import ImageIngestConfig, ToolBins, VideoIngestConfig
from ingest.errors import IngestError
from jobs.handlers import handle_export, handle_extract, handle_sfm, handle_training
from jobs.models import JobSpec, new_job_record
from jobs.paths import job_paths
from jobs.states import SourceKind, StageStatus
from sceneio.detect import detect_source_kind, skips_reconstruction
from sceneio.document import build_scene_document
from sceneio.export import export_scene, refresh_scene_calibration
from sceneio.ingest import ingest_ply, ingest_scene, validate_ply_header


class _MissingTransform:
    def run(self, argv, *, cwd=None, env=None, timeout_s=None):
        del cwd, env, timeout_s
        if argv and "splat-transform" in str(argv[0]):
            raise FileNotFoundError(argv[0])
        dest = Path(argv[-1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"thumb")
        return SimpleNamespace(returncode=0, stdout="", stderr="")


class _MustNotRun:
    def run(self, *args, **kwargs):
        raise AssertionError("runner should not be called for PLY ingest")


def _ascii_ply(path: Path) -> Path:
    path.write_text(
        "ply\nformat ascii 1.0\nelement vertex 1\nproperty float x\nproperty float y\n"
        "property float z\nend_header\n0 0 0\n",
        encoding="utf-8",
    )
    return path


def test_detect_single_kinds(tmp_path: Path) -> None:
    assert detect_source_kind([tmp_path / "a.mp4"]) is SourceKind.VIDEO
    assert detect_source_kind([tmp_path / "loop.gif"]) is SourceKind.GIF
    assert detect_source_kind([tmp_path / "scan.ply"]) is SourceKind.PLY
    assert detect_source_kind([tmp_path / "a.jpg", tmp_path / "b.png"]) is SourceKind.IMAGES


def test_detect_rejects_mixed_and_empty() -> None:
    with pytest.raises(IngestError) as mixed:
        detect_source_kind(["a.mp4", "b.jpg"])
    assert mixed.value.code == "AMBIGUOUS_SOURCE"
    with pytest.raises(IngestError) as empty:
        detect_source_kind([])
    assert empty.value.code == "MISSING_SOURCE"
    with pytest.raises(IngestError) as unknown:
        detect_source_kind(["notes.txt"])
    assert unknown.value.code == "INVALID_FORMAT"


def test_skips_reconstruction_only_for_ply() -> None:
    assert skips_reconstruction(SourceKind.PLY) is True
    assert skips_reconstruction(SourceKind.GIF) is False
    assert skips_reconstruction(SourceKind.VIDEO) is False
    assert skips_reconstruction(SourceKind.IMAGES) is False


def test_validate_and_copy_ply(tmp_path: Path) -> None:
    src = _ascii_ply(tmp_path / "in.ply")
    dest = tmp_path / "out" / "source.ply"
    copied = ingest_ply(src, dest)
    assert copied.is_file()
    validate_ply_header(copied)
    bogus = tmp_path / "nope.bin"
    bogus.write_bytes(b"\x00\x01\x02")
    with pytest.raises(IngestError) as exc:
        validate_ply_header(bogus)
    assert exc.value.code == "INVALID_PLY"


def test_ingest_scene_ply_skips_reconstruction(tmp_path: Path) -> None:
    ply = _ascii_ply(tmp_path / "scan.ply")
    spec = JobSpec(
        user_id="u",
        source_kind=SourceKind.PLY,
        source_paths=(ply,),
        user_height_m=1.75,
        work_root=tmp_path / "work",
    )
    record = new_job_record(spec, job_id="ply-1")
    result = ingest_scene(
        [ply],
        job_paths(record.work_path),
        video_ingest=VideoIngestConfig(),
        image_ingest=ImageIngestConfig(),
        tools=ToolBins(),
        runner=_MustNotRun(),
        kind=SourceKind.PLY,
    )
    assert result.skip_reconstruction is True
    assert result.ply_path is not None and result.ply_path.is_file()
    ingest_json = json.loads((job_paths(record.work_path).input_dir / "ingest.json").read_text())
    assert ingest_json["source_kind"] == "ply"


def test_handle_ply_skips_sfm_and_training(tmp_path: Path) -> None:
    ply = _ascii_ply(tmp_path / "scan.ply")
    record = new_job_record(
        JobSpec(
            user_id="u",
            source_kind=SourceKind.PLY,
            source_paths=(ply,),
            user_height_m=1.7,
            work_root=tmp_path / "work",
        ),
        job_id="ply-job",
    )
    extracted = handle_extract(record, lambda *_: None, _MustNotRun())
    assert "ply" in extracted.artifacts
    sfm = handle_sfm(record, lambda *_: None, _MustNotRun())
    assert sfm.skipped is True
    train = handle_training(record, lambda *_: None, _MustNotRun())
    assert train.skipped is True
    record.stages["extracting"].artifacts = extracted.artifacts
    exported = handle_export(record, lambda *_: None, _MissingTransform())
    assert Path(exported.artifacts["scene_json"]).is_file()
    assert Path(exported.artifacts["scene_package"]).is_file()
    document = json.loads(Path(exported.artifacts["scene_json"]).read_text(encoding="utf-8"))
    assert document["schemaVersion"] == 1
    assert document["backgroundSplat"]["format"] == "ply"
    assert document["temporal"]["sourceKind"] == "none"
    assert document["relight"]["mode"] == "unsupported"
    with zipfile.ZipFile(exported.artifacts["scene_package"]) as archive:
        names = set(archive.namelist())
    assert "master.ply" in names
    assert "scene.json" in names


def test_export_scene_writes_json_and_zip(tmp_path: Path) -> None:
    ply = _ascii_ply(tmp_path / "src.ply")
    export_dir = tmp_path / "export"
    result = export_scene(
        ExportConfig(),
        source_ply=ply,
        export_dir=export_dir,
        runner=_MissingTransform(),
        scene_id="scene-1",
        scene_name="Sala",
        temporal={
            "enabled": True,
            "frameCount": 12,
            "durationS": 1.2,
            "fps": 10.0,
            "currentTime": 0.0,
            "sourceKind": "gif",
        },
    )
    assert result.scene_json.is_file()
    assert result.scene_package.is_file()
    assert result.document["temporal"]["sourceKind"] == "gif"
    refresh_scene_calibration(export_dir, {"scaleFactor": 1.5, "source": "manual", "confidence": 1})
    patched = json.loads(result.scene_json.read_text(encoding="utf-8"))
    assert patched["calibration"]["scaleFactor"] == 1.5


def test_build_scene_document_prefers_ksplat_uri() -> None:
    doc = build_scene_document(scene_id="x", name="n", has_ksplat=True)
    assert doc["backgroundSplat"] is not None
    assert doc["backgroundSplat"]["uri"] == "scene.ksplat"
    assert doc["backgroundSplat"]["format"] == "ksplat"


def test_stage_status_skipped_constant() -> None:
    assert StageStatus.SKIPPED.value == "skipped"
