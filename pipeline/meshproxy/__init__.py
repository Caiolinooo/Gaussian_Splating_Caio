"""Proxy triangle mesh from 3DGS Gaussian centres (Fase 5, MVP).

Splats have no UV atlas. Overlays (``@gs/overlays``) project onto this
mesh. MVP: Poisson / marching-cubes over Gaussian centres via Open3D.
Future: SuGaR / 2DGS.

Public entry points
-------------------
* ``read_gaussian_ply`` — stdlib 3DGS PLY parser
* ``filter_cloud`` / ``opacity_sigmoid`` — stdlib cleanup
* ``prepare_cloud`` / ``assert_min_points`` — quality gate (no Open3D)
* ``build_proxy`` — Poisson → GLB (raises ``BackendUnavailableError``
  when Open3D is missing)
* ``meshproxy_stage`` — job-stage contract for ``pipeline/jobs``
"""

from __future__ import annotations

from ._deps import AVAILABLE
from .errors import BackendUnavailableError, MeshProxyError, SparseCloudError
from .filtering import (
    FilterResult,
    filter_cloud,
    knn_neighbors,
    opacity_sigmoid,
)
from .io_ply import GaussianCloud, read_gaussian_ply
from .reconstruct import (
    PreparedCloud,
    ProxyBuildResult,
    build_proxy,
    prepare_cloud,
)
from .stage import (
    MeshProxyContext,
    MeshProxyStageResult,
    make_stage_result,
    meshproxy_stage,
)

__all__ = [
    "AVAILABLE",
    "BackendUnavailableError",
    "FilterResult",
    "GaussianCloud",
    "MeshProxyContext",
    "MeshProxyError",
    "MeshProxyStageResult",
    "PreparedCloud",
    "ProxyBuildResult",
    "SparseCloudError",
    "build_proxy",
    "filter_cloud",
    "knn_neighbors",
    "make_stage_result",
    "meshproxy_stage",
    "opacity_sigmoid",
    "prepare_cloud",
    "read_gaussian_ply",
]
__version__ = "0.2.0"
