"""Export configuration: master PLY + web KSPLAT + thumbnails."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportConfig:
    splat_transform_bin: str = "splat-transform"
    ffmpeg_bin: str = "ffmpeg"
    filter_nan: bool = True
    filter_floaters: bool = True
    floater_voxel: float = 0.05
    floater_opacity: float = 0.1
    floater_min_contribution: float = 0.004
    web_sh_degree: int | None = 2
    thumbnail_max_edge: int = 512
    thumbnail_name: str = "preview.jpg"
    timeout_s: float | None = None

    def __post_init__(self) -> None:
        if self.thumbnail_max_edge < 16:
            raise ValueError("thumbnail_max_edge must be >= 16")
        if self.web_sh_degree is not None and self.web_sh_degree not in {0, 1, 2, 3}:
            raise ValueError("web_sh_degree must be 0..3 or None")
