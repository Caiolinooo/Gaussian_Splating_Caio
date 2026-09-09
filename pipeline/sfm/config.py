"""COLMAP runner configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

MatcherName = Literal["auto", "exhaustive", "sequential"]
CameraModel = Literal["SIMPLE_PINHOLE", "PINHOLE", "SIMPLE_RADIAL", "OPENCV"]
SourceKind = Literal["video", "images"]

# Vídeo curto (Teams, celular) costuma extrair dezenas/centenas de frames
# quase iguais. O 3DGS treina no subconjunto registrado — não exige 70%.
VIDEO_MIN_REGISTERED_RATIO = 0.40


@dataclass(frozen=True)
class ColmapConfig:
    colmap_bin: str = "colmap"
    matcher: MatcherName = "auto"
    camera_model: CameraModel = "SIMPLE_RADIAL"
    single_camera: bool = True
    use_gpu: bool = True
    sequential_overlap: int = 20
    sequential_quadratic_overlap: bool = True
    min_registered_ratio: float = 0.70
    min_registered_count: int = 20
    max_exhaustive_images: int = 220
    timeout_s: float | None = None
    # NÃO use max_num_models=1: no job 0284bca6 o primeiro modelo era lixo
    # (5 câmeras) e o útil era sparse/3 (90). O runner promove o maior.
    mapper_multiple_models: bool = True
    mapper_max_num_models: int = 8
    mapper_init_num_trials: int = 25
    mapper_ba_global_max_num_iterations: int = 25
    sift_peak_threshold: float | None = 0.004
    sift_edge_threshold: float | None = 10.0
    sift_max_num_features: int | None = 8192

    def __post_init__(self) -> None:
        if not 0.0 < self.min_registered_ratio <= 1.0:
            raise ValueError("min_registered_ratio must be in (0, 1]")
        if self.min_registered_count < 2:
            raise ValueError("min_registered_count must be >= 2")
        if self.sequential_overlap < 1:
            raise ValueError("sequential_overlap must be >= 1")
        if self.max_exhaustive_images < 2:
            raise ValueError("max_exhaustive_images must be >= 2")
        if self.mapper_max_num_models < 1:
            raise ValueError("mapper_max_num_models must be >= 1")
        if self.mapper_init_num_trials < 1:
            raise ValueError("mapper_init_num_trials must be >= 1")
        if self.mapper_ba_global_max_num_iterations < 1:
            raise ValueError("mapper_ba_global_max_num_iterations must be >= 1")

    def resolve_matcher(
        self,
        source_kind: SourceKind,
        image_count: int | None = None,
    ) -> Literal["exhaustive", "sequential"]:
        if self.matcher != "auto":
            return self.matcher
        if image_count is not None and image_count >= 2:
            if image_count <= self.max_exhaustive_images:
                return "exhaustive"
            return "sequential"
        if source_kind == "video":
            return "sequential"
        return "exhaustive"

    def effective_min_registered_ratio(self, source_kind: SourceKind) -> float:
        """Ratio alvo para aviso; vídeo usa um teto mais baixo que o default 70%."""
        if source_kind == "video":
            return min(self.min_registered_ratio, VIDEO_MIN_REGISTERED_RATIO)
        return self.min_registered_ratio


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
