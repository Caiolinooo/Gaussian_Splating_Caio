"""``AutocalHook`` that calls ``autocal.run_auto_calibration``.

Never fails the job: missing pose/depth backends degrade to a
low-confidence identity result (same contract as the autocal service).

``ColmapDepthProvider`` is a documented stub — COLMAP ``cameras.bin`` /
depth maps are not parsed here. The autocal package already ships a
heuristic camera-distance fallback used when SfM depth is unavailable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jobs.autocal import AutocalContext, AutocalResult

LOGGER = logging.getLogger("pipeline.jobs.autocal_adapter")

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"})

_FALLBACK_MESSAGE = "Auto-calibração indisponível; use a trena no viewer para definir a escala."


class ColmapDepthProvider:
    """Documented stub for a future COLMAP-backed ``DepthProvider``.

    A real implementation would sample ``Z`` + ``f_y`` from ``cameras.bin``
    and per-view depth maps, keyed by ingest/COLMAP image names.

    ``sample_depth`` always returns ``None`` so callers that inject this
    stub get the same path as ``depth_provider=None`` (no-depth warning).
    Prefer ``HeuristicCameraDistanceProvider`` from ``autocal.depth`` until
    COLMAP depth is wired.
    """

    is_heuristic = True

    def sample_depth(
        self,
        frame_id: str,
        x_norm: float,
        y_norm: float,
        *,
        image_size: tuple[int, int] | None = None,
    ) -> None:
        del frame_id, x_norm, y_norm, image_size
        return None

    def person_height_scene_units(
        self,
        frame_id: str,
        crown_xy_norm: tuple[float, float],
        feet_xy_norm: tuple[float, float],
        image_size: tuple[int, int],
    ) -> None:
        del frame_id, crown_xy_norm, feet_xy_norm, image_size
        return None


def _fallback_result(*, warnings: list[str] | None = None) -> AutocalResult:
    notes = list(warnings or [_FALLBACK_MESSAGE])
    scene: dict[str, Any] = {
        "scaleFactor": None,
        "source": "none",
        "confidence": 0.0,
        "framesUsed": 0,
        "estimatedPersonHeightSceneUnits": None,
        "errorEstimate": None,
        "warnings": notes,
    }
    return AutocalResult(
        scale_factor=None,
        source="none",
        confidence=0.0,
        frames_used=0,
        message=_FALLBACK_MESSAGE,
        scene_calibration=scene,
    )


def _load_frames(frames_dir: Path) -> list[Any]:
    from autocal.types import FrameInput

    if not frames_dir.is_dir():
        return []
    frames: list[Any] = []
    for path in sorted(frames_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        frames.append(
            FrameInput(
                frame_id=path.name,
                width=1920,
                height=1080,
                image=None,
            )
        )
    return frames


def _message_from_result(result: Any) -> str:
    warnings = list(getattr(result, "warnings", None) or [])
    confidence = float(getattr(result, "confidence", 0.0) or 0.0)
    frames_used = int(getattr(result, "frames_used", 0) or 0)
    if confidence <= 0.0:
        if warnings:
            return warnings[0]
        return _FALLBACK_MESSAGE
    return (
        f"Escala candidata estimada com confiança {confidence:.0%} "
        f"({frames_used} frames)."
    )


class PipelineAutocal:
    """Production ``AutocalHook``: pose service + heuristic depth, never raises."""

    def run(self, context: AutocalContext) -> AutocalResult:
        try:
            return self._run(context)
        except Exception:
            LOGGER.exception("event=autocal_adapter_fallback job_id=%s", context.job_id)
            return _fallback_result()

    def _run(self, context: AutocalContext) -> AutocalResult:
        try:
            from autocal.depth import HeuristicCameraDistanceProvider
            from autocal.models import CalibrationResult
            from autocal.service import run_auto_calibration
        except ImportError as exc:
            LOGGER.info("event=autocal_import_failed err=%s", exc)
            return _fallback_result(
                warnings=["Pacote de auto-calibração indisponível neste ambiente."]
            )

        frames = _load_frames(Path(context.frames_dir))
        depth = HeuristicCameraDistanceProvider()
        try:
            result = run_auto_calibration(
                frames,
                context.user_height_m,
                depth_provider=depth,
            )
        except ValueError:
            result = CalibrationResult.failed_auto(["Altura do usuário inválida."])

        mapped_source = result.source if result.source in {"auto-height", "manual"} else "none"
        return AutocalResult(
            scale_factor=result.scale_factor,
            source=mapped_source,  # type: ignore[arg-type]
            confidence=result.confidence,
            frames_used=result.frames_used,
            message=_message_from_result(result),
            scene_calibration=result.to_scene_dict(),
        )
