"""Single export entry: master PLY + optional ksplat + scene.json + scene.zip."""

from __future__ import annotations

import json
import logging
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from export.config import ExportConfig
from export.runner import CommandRunner, run_export
from sceneio.document import (
    RelightDocument,
    SceneDocumentDict,
    TemporalDocument,
    build_scene_document,
    default_relight,
    default_temporal,
)

LOGGER = logging.getLogger("pipeline.sceneio.export")

ProgressFn = Callable[[float, str], None]


@dataclass(frozen=True)
class SceneExportResult:
    master_ply: Path
    web_ksplat: Path
    thumbnail: Path | None
    scene_json: Path
    scene_package: Path
    document: SceneDocumentDict
    ksplat_written: bool


def _load_calibration(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def export_scene(
    config: ExportConfig,
    *,
    source_ply: Path,
    export_dir: Path,
    runner: CommandRunner,
    scene_id: str,
    scene_name: str = "Cena",
    render_dir: Path | None = None,
    frames_dir: Path | None = None,
    calibration_path: Path | None = None,
    temporal: TemporalDocument | None = None,
    relight: RelightDocument | None = None,
    progress: ProgressFn | None = None,
) -> SceneExportResult:
    """Wraps `run_export` and writes the interoperable scene document + zip."""
    if progress is not None:
        progress(0.05, "Exportando splat…")
    splat = run_export(
        config,
        source_ply=source_ply,
        export_dir=export_dir,
        runner=runner,
        render_dir=render_dir,
        frames_dir=frames_dir,
        progress=progress,
    )
    ksplat_written = splat.web_ksplat.is_file()
    calibration = _load_calibration(calibration_path) if calibration_path else None
    document = build_scene_document(
        scene_id=scene_id,
        name=scene_name,
        has_ksplat=ksplat_written,
        calibration=calibration,
        temporal=temporal if temporal is not None else default_temporal(),
        relight=relight if relight is not None else default_relight(),
    )
    scene_json = export_dir / "scene.json"
    scene_json.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    if progress is not None:
        progress(0.92, "Empacotando cena…")
    package = export_dir / "scene.zip"
    _write_package(
        package,
        master_ply=splat.master_ply,
        web_ksplat=splat.web_ksplat if ksplat_written else None,
        scene_json=scene_json,
        calibration_path=calibration_path if calibration_path and calibration_path.is_file() else None,
        thumbnail=splat.thumbnail,
    )
    if progress is not None:
        progress(1.0, "Cena exportada (PLY + JSON + pacote).")
    LOGGER.info(
        "event=export_scene ply=%s ksplat=%s json=%s zip=%s",
        splat.master_ply,
        splat.web_ksplat if ksplat_written else None,
        scene_json,
        package,
    )
    return SceneExportResult(
        master_ply=splat.master_ply,
        web_ksplat=splat.web_ksplat,
        thumbnail=splat.thumbnail,
        scene_json=scene_json,
        scene_package=package,
        document=document,
        ksplat_written=ksplat_written,
    )


def _write_package(
    dest: Path,
    *,
    master_ply: Path,
    web_ksplat: Path | None,
    scene_json: Path,
    calibration_path: Path | None,
    thumbnail: Path | None,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(master_ply, "master.ply")
        archive.write(scene_json, "scene.json")
        if web_ksplat is not None and web_ksplat.is_file():
            archive.write(web_ksplat, "scene.ksplat")
        if calibration_path is not None:
            archive.write(calibration_path, "calibration.json")
        if thumbnail is not None and thumbnail.is_file():
            archive.write(thumbnail, f"thumbnails/{thumbnail.name}")


def refresh_scene_calibration(export_dir: Path, calibration: dict[str, Any]) -> None:
    """Patch scene.json + zip after autocal (export runs before that stage)."""
    scene_json = export_dir / "scene.json"
    if not scene_json.is_file():
        return
    try:
        document = json.loads(scene_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(document, dict):
        return
    document["calibration"] = calibration
    scene_json.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    calib = export_dir / "calibration.json"
    calib.write_text(json.dumps(calibration, indent=2, ensure_ascii=False), encoding="utf-8")
    package = export_dir / "scene.zip"
    master = export_dir / "master.ply"
    ksplat = export_dir / "scene.ksplat"
    thumbs = export_dir / "thumbnails" / "preview.jpg"
    if master.is_file():
        _write_package(
            package,
            master_ply=master,
            web_ksplat=ksplat if ksplat.is_file() else None,
            scene_json=scene_json,
            calibration_path=calib if calib.is_file() else None,
            thumbnail=thumbs if thumbs.is_file() else None,
        )
