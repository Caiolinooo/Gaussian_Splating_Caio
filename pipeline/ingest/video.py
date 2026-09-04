"""Video intake: ffmpeg extract → blur/dedup → normalize listing."""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ingest.adaptive import AdaptiveRate, compute_adaptive_rate, format_fps
from ingest.config import ToolBins, VideoIngestConfig, VideoProbe
from ingest.errors import IngestError, too_few_frames, video_unreadable
from ingest.probe import build_ffprobe_command, parse_ffprobe_json
from ingest.quality import (
    FrameScore,
    FrameSelection,
    compute_normalized_size,
    laplacian_variance,
    perceptual_signature,
    select_frames,
)

try:
    from PIL import Image
except ImportError:  # optional at unit-test time
    Image = None

LOGGER = logging.getLogger("pipeline.ingest.video")

ProgressFn = Callable[[float, str], None]


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_s: float | None = None,
    ) -> CommandResult: ...


ScoreFn = Callable[[Path, int], FrameScore]


@dataclass(frozen=True)
class VideoIngestResult:
    probe: VideoProbe
    rate: AdaptiveRate
    selection: FrameSelection
    frames_dir: Path
    raw_dir: Path
    kept_paths: tuple[Path, ...]
    normalize_size: tuple[int, int]
    extract_argv: tuple[str, ...]
    probe_argv: tuple[str, ...]


def build_ffmpeg_extract_command(
    ffmpeg: str,
    source: Path,
    output_pattern: Path,
    *,
    fps: float,
    max_edge: int,
    jpeg_quality: int = 2,
) -> list[str]:
    """Extract JPEG frames at ``fps``, letterboxed to an even ``max_edge``."""
    edge = max(int(max_edge), 2)
    if edge % 2:
        edge -= 1
    vf = (
        f"fps={format_fps(fps)},"
        f"scale={edge}:{edge}:force_original_aspect_ratio=decrease,"
        "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    )
    return [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-i",
        str(source),
        "-vf",
        vf,
        "-q:v",
        str(jpeg_quality),
        str(output_pattern),
    ]


def load_gray(path: Path) -> list[list[float]]:
    if Image is None:
        raise IngestError(
            "Pillow is not installed",
            user_message="Falta o componente de leitura de imagens no ambiente.",
            code="MISSING_PIL",
        )
    with Image.open(path) as handle:
        gray = handle.convert("L")
        width, height = gray.size
        pixels = list(gray.getdata())
    return [
        [float(pixels[y * width + x]) for x in range(width)]
        for y in range(height)
    ]


def score_frame(path: Path, index: int, *, signature_size: int = 8) -> FrameScore:
    pixels = load_gray(path)
    return FrameScore(
        index=index,
        path=str(path),
        sharpness=laplacian_variance(pixels),
        signature=perceptual_signature(pixels, size=signature_size),
    )


def _emit(progress: ProgressFn | None, fraction: float, message: str) -> None:
    if progress is not None:
        progress(max(0.0, min(1.0, fraction)), message)
    LOGGER.info("event=ingest_video_progress progress=%.3f message=%s", fraction, message)


def ingest_video(
    source: Path,
    output_dir: Path,
    config: VideoIngestConfig,
    tools: ToolBins,
    runner: CommandRunner,
    *,
    progress: ProgressFn | None = None,
    score_fn: ScoreFn | None = None,
    min_keep: int | None = None,
) -> VideoIngestResult:
    """Run the video intake pipeline. ``runner`` must execute ffmpeg/ffprobe."""
    source = source.resolve()
    if not source.is_file():
        raise video_unreadable(str(source), "file not found")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    frames_dir = output_dir / "kept"
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    raw_dir.mkdir(parents=True)
    frames_dir.mkdir(parents=True)

    probe_argv = build_ffprobe_command(tools.ffprobe, source)
    _emit(progress, 0.05, "Lendo metadados do vídeo…")
    LOGGER.info("event=ffprobe_start argv=%s", " ".join(probe_argv))
    probed = runner.run(probe_argv)
    if probed.returncode != 0:
        raise video_unreadable(source.name, probed.stderr.strip() or "ffprobe failed")
    try:
        payload = json.loads(probed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise video_unreadable(source.name, "ffprobe JSON inválido") from exc
    if not isinstance(payload, dict):
        raise video_unreadable(source.name, "ffprobe JSON inválido")
    probe = parse_ffprobe_json(payload, source=source)

    rate = compute_adaptive_rate(
        probe.duration_s,
        probe.fps,
        target_min=config.target_min_frames,
        target_max=config.target_max_frames,
        oversample=config.oversample,
    )
    normalize = compute_normalized_size(probe.width, probe.height, max_edge=config.max_edge_px)
    pattern = raw_dir / "frame_%06d.jpg"
    extract_argv = build_ffmpeg_extract_command(
        tools.ffmpeg,
        source,
        pattern,
        fps=rate.extract_fps,
        max_edge=config.max_edge_px,
        jpeg_quality=config.jpeg_quality,
    )
    _emit(progress, 0.2, "Extraindo frames…")
    LOGGER.info(
        "event=ffmpeg_extract_start strategy=%s extract_fps=%s expected=%s argv=%s",
        rate.strategy,
        format_fps(rate.extract_fps),
        rate.expected_extract_count,
        " ".join(extract_argv),
    )
    extracted = runner.run(extract_argv)
    if extracted.returncode != 0:
        raise video_unreadable(source.name, extracted.stderr.strip() or "ffmpeg failed")

    raw_frames = tuple(sorted(raw_dir.glob("frame_*.jpg")))
    if not raw_frames:
        raise video_unreadable(source.name, "ffmpeg produced no frames")

    scorer = score_fn or (lambda path, index: score_frame(path, index, signature_size=config.signature_size))
    scores = [scorer(path, index) for index, path in enumerate(raw_frames)]
    _emit(progress, 0.7, "Filtrando frames tremidos e repetidos…")
    selection = select_frames(
        scores,
        blur_threshold=config.blur_threshold,
        relaxed_blur_threshold=config.relaxed_blur_threshold,
        dedup_threshold=config.dedup_threshold,
        target_min=config.target_min_frames,
        target_max=config.target_max_frames,
    )

    floor = config.target_min_frames if min_keep is None else min_keep
    if len(selection.kept) < floor:
        raise too_few_frames(len(selection.kept), floor)

    kept_paths: list[Path] = []
    for order, item in enumerate(selection.kept, start=1):
        dest = frames_dir / f"frame_{order:06d}.jpg"
        shutil.copy2(item.path, dest)
        kept_paths.append(dest)

    manifest = {
        "source": str(source),
        "probe": {
            "width": probe.width,
            "height": probe.height,
            "duration_s": probe.duration_s,
            "fps": probe.fps,
        },
        "rate": {
            "strategy": rate.strategy,
            "extract_fps": rate.extract_fps,
            "expected_extract_count": rate.expected_extract_count,
            "target_keep_count": rate.target_keep_count,
            "warning": rate.warning,
        },
        "normalize_size": list(normalize),
        "kept": [str(path) for path in kept_paths],
        "dropped_blur": len(selection.dropped_blur),
        "dropped_dup": len(selection.dropped_dup),
        "dropped_overflow": len(selection.dropped_overflow),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _emit(progress, 1.0, f"{len(kept_paths)} frames prontos.")
    LOGGER.info(
        "event=ingest_video_done kept=%s blur=%s dup=%s overflow=%s",
        len(kept_paths),
        len(selection.dropped_blur),
        len(selection.dropped_dup),
        len(selection.dropped_overflow),
    )
    return VideoIngestResult(
        probe=probe,
        rate=rate,
        selection=selection,
        frames_dir=frames_dir,
        raw_dir=raw_dir,
        kept_paths=tuple(kept_paths),
        normalize_size=normalize,
        extract_argv=tuple(extract_argv),
        probe_argv=tuple(probe_argv),
    )
