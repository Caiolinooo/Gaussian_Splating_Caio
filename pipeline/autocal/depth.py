"""Depth / metric-scale providers that convert pixel stature → scene units.

COLMAP reconstructions have an **arbitrary global scale**. A vertical object of
pixel height ``Δv`` (pixels) standing at depth ``Z`` (scene units) in a
pinhole camera with vertical focal length ``f_y`` (pixels) has height

    H_scene = Δv * Z / f_y

in the same units as ``Z``. Derivation: the pinhole projection
``v = f_y * Y / Z + c_y`` implies ``ΔY = Δv * Z / f_y`` when ``Z`` is
approximately constant along the person (frontal standing pose).

This package does **not** import ``pipeline/sfm``. The jobs/SfM owner should
implement ``DepthProvider`` by reading COLMAP ``cameras.bin`` (``f_y``,
``c_y``) plus a depth map or a triangulated sample at the person's torso.
Plug that object into ``run_auto_calibration(..., depth_provider=...)``.

When no SfM depth is available, ``HeuristicCameraDistanceProvider`` assumes a
camera-to-person distance and a vertical FOV. The service then down-weights
confidence and emits a pt-BR warning — the tape measure remains authoritative.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DepthSample:
    """Depth and intrinsics at one normalized image point.

    Attributes
    ----------
    depth_scene_units:
        Camera-space ``Z`` in COLMAP / reconstruction units.
    focal_length_y_px:
        ``f_y`` in pixels.
    principal_point_y_norm:
        ``c_y / image_height``. Default 0.5 (image centre).
    is_heuristic:
        True when ``Z`` / ``f_y`` were guessed rather than measured.
    """

    depth_scene_units: float
    focal_length_y_px: float
    principal_point_y_norm: float = 0.5
    is_heuristic: bool = False


class DepthProvider(ABC):
    """Convert a pixel-space person height into reconstruction units.

    Integration (do **not** import sibling pipeline packages from autocal):

    * ``pipeline/sfm`` — after COLMAP, implement a provider that samples a
      depth map (or sparse depth) per ``frame_id`` matching ingest/COLMAP
      image names, and returns the camera ``f_y``.
    * ``pipeline/ingest`` — ``frame_id`` / resolution come from extracted
      frames; this provider is keyed by those ids.
    * Heuristic fallback — ``HeuristicCameraDistanceProvider`` when SfM depth
      is missing (low confidence).
    """

    @property
    def is_heuristic(self) -> bool:
        return False

    @abstractmethod
    def sample_depth(
        self,
        frame_id: str,
        x_norm: float,
        y_norm: float,
        *,
        image_size: tuple[int, int] | None = None,
    ) -> DepthSample | None:
        """Return ``Z`` and ``f_y`` at a normalized image point, or ``None``."""

    def person_height_scene_units(
        self,
        frame_id: str,
        crown_xy_norm: tuple[float, float],
        feet_xy_norm: tuple[float, float],
        image_size: tuple[int, int],
    ) -> float | None:
        """Default pinhole conversion. Override to triangulate two rays.

        Samples depth at the mid-body point (average of crown and feet) and
        applies ``H = Δv_px * Z / f_y``. A COLMAP-backed override can
        unproject crown and feet with per-point depth and take
        ``||P_crown - P_feet||`` (or the world-up component) instead.
        """
        width, height = image_size
        if height <= 0 or width <= 0:
            return None
        mid_x = 0.5 * (crown_xy_norm[0] + feet_xy_norm[0])
        mid_y = 0.5 * (crown_xy_norm[1] + feet_xy_norm[1])
        sample = self.sample_depth(frame_id, mid_x, mid_y, image_size=image_size)
        if sample is None or sample.focal_length_y_px <= 1e-9:
            return None
        pixel_height = abs(feet_xy_norm[1] - crown_xy_norm[1]) * float(height)
        return pixel_height * sample.depth_scene_units / sample.focal_length_y_px


class ConstantDepthProvider(DepthProvider):
    """Fixed ``Z`` and ``f_y`` — intended for tests and deterministic fixtures."""

    def __init__(
        self,
        depth_scene_units: float,
        focal_length_y_px: float,
        *,
        heuristic: bool = False,
    ) -> None:
        if depth_scene_units <= 0.0:
            raise ValueError("depth_scene_units must be > 0")
        if focal_length_y_px <= 0.0:
            raise ValueError("focal_length_y_px must be > 0")
        self._depth = depth_scene_units
        self._fy = focal_length_y_px
        self._heuristic = heuristic

    @property
    def is_heuristic(self) -> bool:
        return self._heuristic

    def sample_depth(
        self,
        frame_id: str,
        x_norm: float,
        y_norm: float,
        *,
        image_size: tuple[int, int] | None = None,
    ) -> DepthSample:
        del frame_id, x_norm, y_norm, image_size
        return DepthSample(
            depth_scene_units=self._depth,
            focal_length_y_px=self._fy,
            is_heuristic=self._heuristic,
        )


class HeuristicCameraDistanceProvider(DepthProvider):
    """Assume a camera-to-person distance and a vertical field of view.

    ``f_y = (H / 2) / tan(FOV_v / 2)``. Marked heuristic so the service can
    penalise confidence. Prefer a COLMAP ``DepthProvider`` whenever possible.
    """

    def __init__(
        self,
        camera_distance_scene_units: float = 3.0,
        vertical_fov_degrees: float = 60.0,
    ) -> None:
        if camera_distance_scene_units <= 0.0:
            raise ValueError("camera_distance_scene_units must be > 0")
        if not 1.0 < vertical_fov_degrees < 179.0:
            raise ValueError("vertical_fov_degrees must be in (1, 179)")
        self._distance = camera_distance_scene_units
        self._fov_rad = math.radians(vertical_fov_degrees)

    @property
    def is_heuristic(self) -> bool:
        return True

    def sample_depth(
        self,
        frame_id: str,
        x_norm: float,
        y_norm: float,
        *,
        image_size: tuple[int, int] | None = None,
    ) -> DepthSample:
        del frame_id, x_norm, y_norm
        image_height = float(image_size[1]) if image_size is not None else 1080.0
        fy = (image_height / 2.0) / math.tan(self._fov_rad / 2.0)
        return DepthSample(
            depth_scene_units=self._distance,
            focal_length_y_px=fy,
            is_heuristic=True,
        )
