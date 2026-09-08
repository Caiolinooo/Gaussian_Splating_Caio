"""Single ingest entry. Dispatches by SourceKind; does not fork pipelines."""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ingest.config import ImageIngestConfig, ToolBins, VideoIngestConfig
from ingest.errors import IngestError
from ingest.images import ingest_images
from ingest.video import CommandRunner, ingest_video
from jobs.paths import JobPaths
from jobs.states import SourceKind, assert_never
from sceneio.detect import detect_source_kind
from sceneio.document import TemporalDocument, default_temporal

LOGGER = logging.getLogger("pipeline.sceneio.ingest")

ProgressFn = Callable[[float, str], None]


def invalid_ply(path: str, detail: str) -> IngestError:
    return IngestError(
        f"invalid ply: {path}: {detail}",
        user_message=(
            "O arquivo .ply não parece um splat Gaussian Splatting válido. "
            "Envie um PLY com cabeçalho `ply` (export de 3DGS / SuperSplat / COLMAP)."
        ),
        code="INVALID_PLY",
    )


@dataclass(frozen=True)
class SceneIngestResult:
    source_kind: SourceKind
    frames_dir: Path | None
    kept_paths: tuple[Path, ...]
    ply_path: Path | None
    temporal: TemporalDocument
    artifacts: dict[str, str]
    metrics: dict[str, object]
    message: str
    skip_reconstruction: bool


def validate_ply_header(path: Path) -> None:
    if not path.is_file():
        raise invalid_ply(str(path), "file not found")
    if path.stat().st_size < 4:
        raise invalid_ply(str(path), "too small")
    with path.open("rb") as handle:
        magic = handle.read(4)
    if not magic.lower().startswith(b"ply"):
        raise invalid_ply(str(path), "missing ply magic")


def ingest_ply(source: Path, dest: Path, *, progress: ProgressFn | None = None) -> Path:
    source = source.resolve()
    validate_ply_header(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if progress is not None:
        progress(0.4, "Importando splat .ply…")
    if source.resolve() != dest.resolve():
        shutil.copy2(source, dest)
    if progress is not None:
        progress(1.0, "PLY importado.")
    LOGGER.info("event=ingest_ply dest=%s bytes=%s", dest, dest.stat().st_size)
    return dest


def _temporal_from_video(
    *,
    kind: SourceKind,
    frame_count: int,
    duration_s: float | None,
    fps: float | None,
) -> TemporalDocument:
    source = "gif" if kind is SourceKind.GIF else "video"
    enabled = kind is SourceKind.GIF or (frame_count > 1 and duration_s is not None and duration_s > 0)
    return {
        "enabled": enabled,
        "frameCount": frame_count,
        "durationS": duration_s,
        "fps": fps,
        "currentTime": 0.0,
        "sourceKind": source if enabled else "none",
    }


def ingest_scene(
    sources: Sequence[Path | str],
    paths: JobPaths,
    *,
    video_ingest: VideoIngestConfig,
    image_ingest: ImageIngestConfig,
    tools: ToolBins,
    runner: CommandRunner,
    progress: ProgressFn | None = None,
    kind: SourceKind | None = None,
) -> SceneIngestResult:
    """Unified ingest. `kind` is optional — detector fills it from filenames."""
    resolved = [Path(item) for item in sources]
    detected = kind or detect_source_kind(resolved)
    paths.ensure()
    ingest_dir = paths.input_dir
    ingest_dir.mkdir(parents=True, exist_ok=True)

    if detected is SourceKind.PLY:
        dest = ingest_dir / "source.ply"
        ply = ingest_ply(resolved[0], dest, progress=progress)
        temporal = default_temporal()
        payload = {
            "source_kind": detected.value,
            "ply": str(ply),
            "temporal": temporal,
        }
        manifest = ingest_dir / "ingest.json"
        manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return SceneIngestResult(
            source_kind=detected,
            frames_dir=None,
            kept_paths=(),
            ply_path=ply,
            temporal=temporal,
            artifacts={"ply": str(ply), "ingest": str(manifest)},
            metrics={"bytes": ply.stat().st_size, "skip_reconstruction": True},
            message="PLY importado — SfM e treino serão pulados.",
            skip_reconstruction=True,
        )

    if detected is SourceKind.VIDEO or detected is SourceKind.GIF:
        min_keep = 1 if detected is SourceKind.GIF else None
        result = ingest_video(
            resolved[0],
            paths.frames_dir,
            video_ingest,
            tools,
            runner,
            progress=progress,
            min_keep=min_keep,
        )
        temporal = _temporal_from_video(
            kind=detected,
            frame_count=len(result.kept_paths),
            duration_s=result.probe.duration_s,
            fps=result.rate.extract_fps,
        )
        manifest = paths.frames_dir / "manifest.json"
        extra = ingest_dir / "ingest.json"
        extra.write_text(
            json.dumps(
                {
                    "source_kind": detected.value,
                    "frames_dir": str(result.frames_dir),
                    "temporal": temporal,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        label = "GIF" if detected is SourceKind.GIF else "vídeo"
        return SceneIngestResult(
            source_kind=detected,
            frames_dir=result.frames_dir,
            kept_paths=result.kept_paths,
            ply_path=None,
            temporal=temporal,
            artifacts={
                "frames_dir": str(result.frames_dir),
                "manifest": str(manifest),
                "ingest": str(extra),
            },
            metrics={
                "kept_frames": len(result.kept_paths),
                "strategy": result.rate.strategy,
                "extract_fps": result.rate.extract_fps,
                "dropped_blur": len(result.selection.dropped_blur),
                "dropped_dup": len(result.selection.dropped_dup),
            },
            message=f"{len(result.kept_paths)} frames extraídos do {label}.",
            skip_reconstruction=False,
        )

    if detected is SourceKind.IMAGES:
        result = ingest_images(resolved, paths.images_versions_dir, image_ingest, progress=progress)
        temporal = default_temporal()
        extra = ingest_dir / "ingest.json"
        extra.write_text(
            json.dumps(
                {
                    "source_kind": detected.value,
                    "frames_dir": str(result.version_dir),
                    "temporal": temporal,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return SceneIngestResult(
            source_kind=detected,
            frames_dir=result.version_dir,
            kept_paths=result.copied,
            ply_path=None,
            temporal=temporal,
            artifacts={
                "frames_dir": str(result.version_dir),
                "version": str(result.version),
                "ingest": str(extra),
            },
            metrics={"kept_frames": len(result.copied), "rejected": len(result.rejected)},
            message=f"{len(result.copied)} imagens validadas ({result.version_dir.name}).",
            skip_reconstruction=False,
        )

    assert_never(detected)
