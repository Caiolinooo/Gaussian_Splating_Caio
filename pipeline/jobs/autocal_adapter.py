"""``AutocalHook`` that calls ``autocal.run_auto_calibration``.

Never fails the job: missing pose/depth backends degrade to a
low-confidence identity result (same contract as the autocal service).

``ColmapDepthProvider`` samples sparse Z + f_y from COLMAP ``cameras.txt``,
``images.txt`` and ``points3D.txt``. Sem modelo, devolve ``None`` e o
serviço cai no heurístico.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from autocal.colmap_depth import ColmapSparseDepth
from autocal.depth import DepthSample
from jobs.autocal import AutocalContext, AutocalResult

LOGGER = logging.getLogger("pipeline.jobs.autocal_adapter")

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"})

_FALLBACK_MESSAGE = "Auto-calibração indisponível; use a trena no viewer para definir a escala."


class ColmapDepthProvider:
    """Depth esparsa COLMAP (paredes/chão sem LiDAR) para autocal."""

    def __init__(self, model_dir: Path | str | None = None) -> None:
        self._sparse: ColmapSparseDepth | None = None
        if model_dir:
            path = Path(model_dir)
            if path.is_dir():
                self._sparse = ColmapSparseDepth(path)

    @property
    def is_heuristic(self) -> bool:
        return self._sparse is None

    def sample_depth(
        self,
        frame_id: str,
        x_norm: float,
        y_norm: float,
        *,
        image_size: tuple[int, int] | None = None,
    ) -> DepthSample | None:
        del image_size
        if self._sparse is None:
            return None
        return self._sparse.sample(frame_id, x_norm, y_norm)

    def person_height_scene_units(
        self,
        frame_id: str,
        crown_xy_norm: tuple[float, float],
        feet_xy_norm: tuple[float, float],
        image_size: tuple[int, int],
    ) -> float | None:
        width, height = image_size
        if height <= 0 or width <= 0:
            return None
        mid_x = 0.5 * (crown_xy_norm[0] + feet_xy_norm[0])
        mid_y = 0.5 * (crown_xy_norm[1] + feet_xy_norm[1])
        sample = self.sample_depth(frame_id, mid_x, mid_y, image_size=image_size)
        if sample is None or sample.focal_length_y_px <= 1e-9:
            return None
        pixel_height = abs(feet_xy_norm[1] - crown_xy_norm[1]) * float(height)
        return pixel_height * sample.depth_scene_units / sample.focal_length_y_px


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
    """Production ``AutocalHook``: pose + COLMAP depth, never raises."""

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
        colmap_depth = ColmapDepthProvider(context.colmap_model_dir or None)
        depth = colmap_depth if not colmap_depth.is_heuristic else HeuristicCameraDistanceProvider()
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
