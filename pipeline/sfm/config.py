"""COLMAP runner configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

MatcherName = Literal["auto", "exhaustive", "sequential"]
CameraModel = Literal["SIMPLE_PINHOLE", "PINHOLE", "SIMPLE_RADIAL", "OPENCV"]
SourceKind = Literal["video", "images"]


@dataclass(frozen=True)
class ColmapConfig:
    colmap_bin: str = "colmap"
    matcher: MatcherName = "auto"
    camera_model: CameraModel = "SIMPLE_RADIAL"
    single_camera: bool = True
    use_gpu: bool = True
    sequential_overlap: int = 15
    sequential_quadratic_overlap: bool = True
    min_registered_ratio: float = 0.70
    min_registered_count: int = 20
    timeout_s: float | None = None

    def __post_init__(self) -> None:
        if not 0.0 < self.min_registered_ratio <= 1.0:
            raise ValueError("min_registered_ratio must be in (0, 1]")
        if self.min_registered_count < 2:
            raise ValueError("min_registered_count must be >= 2")
        if self.sequential_overlap < 1:
            raise ValueError("sequential_overlap must be >= 1")

    def resolve_matcher(self, source_kind: SourceKind) -> Literal["exhaustive", "sequential"]:
        if self.matcher == "auto":
            return "sequential" if source_kind == "video" else "exhaustive"
        return self.matcher


@dataclass(frozen=True)
class ColmapPaths:
    image_dir: Path
    work_dir: Path

    @property
    def database(self) -> Path:
        return self.work_dir / "database.db"

    @property
    def sparse_dir(self) -> Path:
        return self.work_dir / "sparse"

    @property
    def model_dir(self) -> Path:
        return self.sparse_dir / "0"
