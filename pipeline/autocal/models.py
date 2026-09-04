"""Pydantic models aligned with the scene JSON calibration object (tasks.md §3/§5).

The viewer and API persist this fragment under ``scene.calibration``:

    {
      "scaleFactor": 0.731,
      "source": "auto-height",
      "confidence": 0.82,
      "framesUsed": 24,
      "estimatedPersonHeightSceneUnits": 2.394,
      "errorEstimate": 0.041,
      "warnings": []
    }

Python attributes are snake_case; ``to_scene_dict()`` emits camelCase aliases.
``source`` is ``"auto-height"`` for this service; ``"manual"`` is reserved for
the live tape measure so the same schema can store either origin.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CalibrationSource = Literal["auto-height", "manual"]


class CalibrationResult(BaseModel):
    """Candidate (or confirmed) metric scale for a reconstructed scene."""

    model_config = ConfigDict(populate_by_name=True)

    scale_factor: float = Field(
        alias="scaleFactor",
        ge=0.0,
        description="Metres per COLMAP/scene unit: user_height / estimated_scene_height.",
    )
    source: CalibrationSource = Field(
        description='Origin of the factor: "auto-height" or "manual".',
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="0–1 score. Viewer skips pre-apply when this is low.",
    )
    frames_used: int = Field(
        alias="framesUsed",
        ge=0,
        description="Inlier frames that contributed to the aggregated height.",
    )
    estimated_person_height_scene_units: float | None = Field(
        default=None,
        alias="estimatedPersonHeightSceneUnits",
        description="Aggregated person height in reconstruction units, or null.",
    )
    error_estimate: float | None = Field(
        default=None,
        alias="errorEstimate",
        description="Robust 1-σ error of scale_factor (same units), or null.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Actionable pt-BR messages for the UI / first-open prompt.",
    )

    def to_scene_dict(self) -> dict[str, Any]:
        """JSON-ready ``scene.calibration`` fragment (camelCase)."""
        return self.model_dump(by_alias=True, mode="json")

    @classmethod
    def failed_auto(cls, warnings: list[str], *, frames_used: int = 0) -> CalibrationResult:
        """Identity scale with confidence 0 — do not pre-apply in the viewer."""
        return cls(
            scale_factor=1.0,
            source="auto-height",
            confidence=0.0,
            frames_used=frames_used,
            estimated_person_height_scene_units=None,
            error_estimate=None,
            warnings=list(warnings),
        )
