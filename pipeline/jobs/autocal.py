"""Auto-calibration hook. Pose/height implementation lives in another service."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

LOGGER = logging.getLogger("pipeline.jobs.autocal")


@dataclass(frozen=True)
class AutocalContext:
    job_id: str
    frames_dir: str
    user_height_m: float
    registered_names: tuple[str, ...]
    colmap_model_dir: str = ""


@dataclass(frozen=True)
class AutocalResult:
    scale_factor: float | None
    source: Literal["auto-height", "manual", "none"]
    confidence: float
    frames_used: int
    message: str
    scene_calibration: dict[str, Any] = field(default_factory=dict)


class AutocalHook(Protocol):
    def run(self, context: AutocalContext) -> AutocalResult: ...


class NoOpAutocal:
    """Placeholder when the pose/height service must stay offline (tests)."""

    def run(self, context: AutocalContext) -> AutocalResult:
        LOGGER.info(
            "event=autocal_noop job_id=%s height_m=%s frames=%s",
            context.job_id,
            context.user_height_m,
            context.frames_dir,
        )
        scene = {
            "scaleFactor": None,
            "source": "none",
            "confidence": 0.0,
            "framesUsed": 0,
            "estimatedPersonHeightSceneUnits": None,
            "errorEstimate": None,
            "warnings": [
                "Auto-calibração ainda não disponível; use a trena no viewer para definir a escala."
            ],
        }
        return AutocalResult(
            scale_factor=None,
            source="none",
            confidence=0.0,
            frames_used=0,
            message=(
                "Auto-calibração ainda não disponível; "
                "use a trena no viewer para definir a escala."
            ),
            scene_calibration=scene,
        )
