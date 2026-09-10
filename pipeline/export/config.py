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
    # Stdlib fallback when splat-transform is missing (needles / floaters).
    cleanup_needles: bool = True
    # 0 = nunca apaga por aniso. Spark precisa de fatten leve (8:1); 4:1 vira bolha.
    max_anisotropy: float = 0.0
    clamp_anisotropy: float = 8.0
    min_opacity_sigmoid: float = 0.02
    max_scale_frac: float = 0.03
    min_scale_frac: float = 0.0
    # Recorta outliers espaciais (floaters longe do núcleo). 0 desliga.
    crop_quantile: float = 0.02
    web_sh_degree: int | None = 3
    thumbnail_max_edge: int = 512
    thumbnail_name: str = "preview.jpg"
    timeout_s: float | None = None

    def __post_init__(self) -> None:
        if self.thumbnail_max_edge < 16:
            raise ValueError("thumbnail_max_edge must be >= 16")
        if self.web_sh_degree is not None and self.web_sh_degree not in {0, 1, 2, 3}:
            raise ValueError("web_sh_degree must be 0..3 or None")
        if self.max_anisotropy < 0:
            raise ValueError("max_anisotropy must be >= 0")
        if self.clamp_anisotropy < 0:
            raise ValueError("clamp_anisotropy must be >= 0")
        if not 0.0 <= self.min_opacity_sigmoid < 1.0:
            raise ValueError("min_opacity_sigmoid must be in [0, 1)")
        if not 0.0 < self.max_scale_frac <= 1.0:
            raise ValueError("max_scale_frac must be in (0, 1]")
        if not 0.0 <= self.min_scale_frac < self.max_scale_frac:
            raise ValueError("min_scale_frac must be in [0, max_scale_frac)")
        if not 0.0 <= self.crop_quantile < 0.5:
            raise ValueError("crop_quantile must be in [0, 0.5)")
