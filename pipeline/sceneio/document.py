"""CamelCase SceneDocument matching `@gs/viewer` (downloadable / interoperable)."""

from __future__ import annotations

from typing import Any, TypedDict


class TemporalDocument(TypedDict):
    enabled: bool
    frameCount: int
    durationS: float | None
    fps: float | None
    currentTime: float
    sourceKind: str


class RelightDocument(TypedDict):
    enabled: bool
    mode: str
    hasSphericalHarmonics: bool
    shDegree: int | None


class SceneDocumentDict(TypedDict):
    schemaVersion: int
    id: str
    name: str
    backgroundSplat: dict[str, Any] | None
    nodes: list[dict[str, Any]]
    calibration: dict[str, Any]
    overlays: list[dict[str, Any]]
    temporal: TemporalDocument
    relight: RelightDocument


DEFAULT_TEMPORAL: TemporalDocument = {
    "enabled": False,
    "frameCount": 0,
    "durationS": None,
    "fps": None,
    "currentTime": 0.0,
    "sourceKind": "none",
}

DEFAULT_RELIGHT: RelightDocument = {
    "enabled": True,
    "mode": "sh-env",
    "hasSphericalHarmonics": True,
    "shDegree": 3,
}

DEFAULT_CALIBRATION: dict[str, Any] = {
    "scaleFactor": None,
    "source": "none",
    "confidence": None,
    "framesUsed": 0,
    "estimatedPersonHeightSceneUnits": None,
    "errorEstimate": None,
    "warnings": [],
}


def default_temporal() -> TemporalDocument:
    return {
        "enabled": False,
        "frameCount": 0,
        "durationS": None,
        "fps": None,
        "currentTime": 0.0,
        "sourceKind": "none",
    }


def default_relight() -> RelightDocument:
    return {
        "enabled": True,
        "mode": "sh-env",
        "hasSphericalHarmonics": True,
        "shDegree": 3,
    }


def build_scene_document(
    *,
    scene_id: str,
    name: str,
    has_ksplat: bool,
    calibration: dict[str, Any] | None = None,
    temporal: TemporalDocument | None = None,
    relight: RelightDocument | None = None,
    overlays: list[dict[str, Any]] | None = None,
) -> SceneDocumentDict:
    fmt = "ksplat" if has_ksplat else "ply"
    uri = "scene.ksplat" if has_ksplat else "master.ply"
    return {
        "schemaVersion": 1,
        "id": scene_id,
        "name": name,
        "backgroundSplat": {
            "id": f"bg-{scene_id}",
            "name": "Splat de fundo",
            "uri": uri,
            "format": fmt,
            "visible": True,
        },
        "nodes": [],
        "calibration": dict(calibration) if calibration else dict(DEFAULT_CALIBRATION),
        "overlays": list(overlays) if overlays else [],
        "temporal": temporal if temporal is not None else default_temporal(),
        "relight": relight if relight is not None else default_relight(),
    }
