"""Versioned scene JSON (snake_case API; mirrors packages/viewer scene schema)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SCENE_SCHEMA_VERSION = 1


class CalibrationSchema(BaseModel):
    scale_factor: float | None = None
    source: Literal["auto-height", "manual", "none"] = "none"
    confidence: float | None = None
    reference: dict[str, Any] | None = None


class SceneNodeSchema(BaseModel):
    id: str
    name: str
    kind: Literal["glb", "splat"]
    uri: str
    format: Literal["glb", "gltf", "ply", "ksplat"]
    visible: bool = True
    locked: bool = False
    trs: dict[str, Any] = Field(default_factory=dict)
    parent_id: str | None = None


class BackgroundSplatSchema(BaseModel):
    id: str
    name: str
    uri: str
    format: Literal["ply", "ksplat"]
    visible: bool = True
    trs: dict[str, Any] | None = None


class OverlaySchema(BaseModel):
    id: str
    name: str
    kind: Literal["decal", "wallpaper", "paint"]
    uri: str
    opacity: float = 1.0
    visible: bool = True


class SceneDocument(BaseModel):
    schema_version: int = SCENE_SCHEMA_VERSION
    version: int = 1
    id: str
    name: str
    job_id: str | None = None
    background_splat: BackgroundSplatSchema | None = None
    nodes: list[SceneNodeSchema] = Field(default_factory=list)
    calibration: CalibrationSchema = Field(default_factory=CalibrationSchema)
    overlays: list[OverlaySchema] = Field(default_factory=list)
    temporal: dict[str, Any] | None = None
    relight: dict[str, Any] | None = None
    updated_at: str | None = None
