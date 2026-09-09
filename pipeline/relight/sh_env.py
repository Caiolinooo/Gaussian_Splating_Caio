"""Spherical-harmonics environment for relight (GaussianCrowds-class control)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RelightEnv:
    enabled: bool
    mode: str
    has_spherical_harmonics: bool
    sh_degree: int
    azimuth_deg: float
    elevation_deg: float
    intensity: float

    def to_document(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "hasSphericalHarmonics": self.has_spherical_harmonics,
            "shDegree": self.sh_degree,
            "azimuthDeg": self.azimuth_deg,
            "elevationDeg": self.elevation_deg,
            "intensity": self.intensity,
        }


def build_relight_env(*, sh_degree: int = 3) -> RelightEnv:
    return RelightEnv(
        enabled=True,
        mode="sh-env",
        has_spherical_harmonics=True,
        sh_degree=sh_degree,
        azimuth_deg=45.0,
        elevation_deg=35.0,
        intensity=1.0,
    )


def write_relight_document(path: Path, env: RelightEnv) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(env.to_document(), indent=2), encoding="utf-8")


def light_direction(azimuth_deg: float, elevation_deg: float) -> tuple[float, float, float]:
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    x = math.cos(el) * math.sin(az)
    y = math.sin(el)
    z = math.cos(el) * math.cos(az)
    length = math.sqrt(x * x + y * y + z * z) or 1.0
    return (x / length, y / length, z / length)


def evaluate_sh_rgb(
    direction: tuple[float, float, float],
    intensity: float,
    base: tuple[float, float, float] = (0.72, 0.70, 0.66),
) -> tuple[float, float, float]:
    """Lambert + warm key. Viewer aplica o mesmo fator em ``recolor``."""
    nx, ny, nz = direction
    lambert = max(0.0, nx * 0.35 + ny * 0.85 + nz * 0.35)
    ambient = 0.35
    scale = ambient + intensity * 0.85 * lambert
    return (
        min(1.8, base[0] * scale * (1.0 + 0.12 * max(0.0, nx))),
        min(1.8, base[1] * scale),
        min(1.8, base[2] * scale * (1.0 + 0.08 * max(0.0, -nx))),
    )
