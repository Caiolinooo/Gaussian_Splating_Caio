"""CalibrationResult serialization matches the scene JSON contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from autocal.models import CalibrationResult


def test_to_scene_dict_uses_camel_case_aliases() -> None:
    result = CalibrationResult(
        scale_factor=0.731,
        source="auto-height",
        confidence=0.82,
        frames_used=24,
        estimated_person_height_scene_units=2.394,
        error_estimate=0.041,
        warnings=[],
    )
    payload = result.to_scene_dict()
    assert payload == {
        "scaleFactor": 0.731,
        "source": "auto-height",
        "confidence": 0.82,
        "framesUsed": 24,
        "estimatedPersonHeightSceneUnits": 2.394,
        "errorEstimate": 0.041,
        "warnings": [],
    }


def test_round_trip_from_scene_json() -> None:
    original = CalibrationResult.model_validate(
        {
            "scaleFactor": 1.0,
            "source": "manual",
            "confidence": 1.0,
            "framesUsed": 0,
            "estimatedPersonHeightSceneUnits": None,
            "errorEstimate": None,
            "warnings": ["ok"],
        }
    )
    restored = CalibrationResult.model_validate(original.to_scene_dict())
    assert restored.source == "manual"
    assert restored.scale_factor == pytest.approx(1.0)
    assert restored.frames_used == 0
    assert restored.warnings == ["ok"]


def test_failed_auto_is_identity_with_zero_confidence() -> None:
    result = CalibrationResult.failed_auto(["Nenhuma pessoa foi detectada nos frames."])
    assert result.scale_factor == 1.0
    assert result.source == "auto-height"
    assert result.confidence == 0.0
    assert result.estimated_person_height_scene_units is None


def test_confidence_must_be_unit_interval() -> None:
    with pytest.raises(ValidationError):
        CalibrationResult(
            scale_factor=1.0,
            source="auto-height",
            confidence=1.5,
            frames_used=0,
        )


def test_source_is_closed_union() -> None:
    with pytest.raises(ValidationError):
        CalibrationResult(
            scale_factor=1.0,
            source="guess",  # type: ignore[arg-type]
            confidence=0.1,
            frames_used=0,
        )
