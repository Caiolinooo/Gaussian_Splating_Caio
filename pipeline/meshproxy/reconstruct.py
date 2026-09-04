"""Prepare a Gaussian cloud and (when Open3D is present) build a proxy mesh.

``prepare_cloud`` is stdlib-only: parse PLY → filter → quality gate.
``build_proxy`` then runs Screened Poisson (Open3D), crops low-density
vertices, simplifies, and writes GLB (OBJ fallback).

Open3D is imported only via ``_deps``. The package import stays clean;
``BackendUnavailableError`` is raised when reconstruction is executed
without the extra.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from ._deps import AVAILABLE, np, o3d
from .errors import (
    BackendUnavailableError,
    empty_mesh,
    export_failed,
    no_faces_after_crop,
    sparse_cloud,
)
from .filtering import (
    DEFAULT_DENSITY_PERCENTILE,
    DEFAULT_KNN_K,
    DEFAULT_OPACITY_THRESHOLD,
    DEFAULT_STD_RATIO,
    estimate_normals,
    filter_cloud,
    normals_are_usable,
)
from .io_ply import read_gaussian_ply
from .types import Vec3

LOGGER = logging.getLogger("pipeline.meshproxy")

DEFAULT_POISSON_DEPTH: int = 9
DEFAULT_SIMPLIFY_TARGET: int = 100_000
DEFAULT_MIN_POINTS: int = 256


@dataclass(frozen=True, slots=True)
class PreparedCloud:
    """Filtered, oriented centres ready for Poisson (or for a quality gate)."""

    points: tuple[Vec3, ...]
    normals: tuple[Vec3, ...]
    points_in: int
    points_filtered: int
    ply_path: Path


@dataclass(frozen=True, slots=True)
class ProxyBuildResult:
    """On-disk proxy mesh plus the metrics the job stage persists."""

    glb_path: Path | None
    obj_path: Path | None
    faces: int
    vertices: int
    points_in: int
    points_filtered: int
    duration_s: float
    method: str = "poisson"


def require_open3d() -> None:
    """Raise ``BackendUnavailableError`` when the optional extra is missing."""
    if not AVAILABLE or o3d is None or np is None:
        raise BackendUnavailableError()


def assert_min_points(count: int, minimum: int) -> None:
    """Quality gate: too few centres after filtering → explainer in pt-BR."""
    if count < minimum:
        raise sparse_cloud(count, minimum)


def prepare_cloud(
    ply_path: str | Path,
    *,
    knn_k: int = DEFAULT_KNN_K,
    std_ratio: float = DEFAULT_STD_RATIO,
    density_percentile: float = DEFAULT_DENSITY_PERCENTILE,
    opacity_threshold: float = DEFAULT_OPACITY_THRESHOLD,
    min_points: int = DEFAULT_MIN_POINTS,
) -> PreparedCloud:
    """Load, clean and gate a 3DGS PLY. Does not import Open3D."""
    path = Path(ply_path)
    cloud = read_gaussian_ply(path)
    filtered = filter_cloud(
        cloud.points,
        opacities=cloud.opacities,
        knn_k=knn_k,
        std_ratio=std_ratio,
        density_percentile=density_percentile,
        opacity_threshold=opacity_threshold,
    )
    assert_min_points(filtered.points_filtered, min_points)

    if normals_are_usable(cloud.normals):
        assert cloud.normals is not None
        normals = tuple(cloud.normals[index] for index in filtered.kept_indices)
    else:
        normals = estimate_normals(filtered.points, knn_k=knn_k)

    return PreparedCloud(
        points=filtered.points,
        normals=normals,
        points_in=filtered.points_in,
        points_filtered=filtered.points_filtered,
        ply_path=path,
    )


def build_proxy(
    ply_path: str | Path,
    out_glb: str | Path,
    *,
    depth: int = DEFAULT_POISSON_DEPTH,
    simplify_target: int = DEFAULT_SIMPLIFY_TARGET,
    density_percentile: float = DEFAULT_DENSITY_PERCENTILE,
    min_points: int = DEFAULT_MIN_POINTS,
    knn_k: int = DEFAULT_KNN_K,
    std_ratio: float = DEFAULT_STD_RATIO,
    opacity_threshold: float = DEFAULT_OPACITY_THRESHOLD,
) -> ProxyBuildResult:
    """Poisson proxy from a 3DGS PLY.

    Parameters
    ----------
    ply_path:
        Master ``.ply`` (Gaussian centres).
    out_glb:
        Destination ``proxy.glb``. If Assimp cannot write GLB, an OBJ
        with the same stem is written instead.
    depth:
        Poisson octree depth (Open3D default is 8; MVP uses 9).
    simplify_target:
        Quadric-decimation face cap. ``0`` skips simplification.
    density_percentile:
        Fraction of *lowest* densities dropped, both on the point cloud
        and on Poisson vertices (Open3D tutorial uses 0.01; MVP 0.1).
    """
    if not 2 <= depth <= 14:
        raise ValueError("depth must be in [2, 14]")
    if not 0.0 <= density_percentile < 1.0:
        raise ValueError("density_percentile must be in [0, 1)")
    if simplify_target < 0:
        raise ValueError("simplify_target must be >= 0")

    started = time.perf_counter()
    prepared = prepare_cloud(
        ply_path,
        knn_k=knn_k,
        std_ratio=std_ratio,
        density_percentile=density_percentile,
        opacity_threshold=opacity_threshold,
        min_points=min_points,
    )
    require_open3d()
    mesh, densities = _poisson_mesh(prepared, depth=depth)
    mesh = _crop_low_density(mesh, densities, density_percentile)
    mesh = _simplify(mesh, simplify_target)

    faces = int(len(mesh.triangles))
    vertices = int(len(mesh.vertices))
    if faces < 1 or vertices < 3:
        raise empty_mesh("no triangles after simplify")

    glb_path, obj_path = _export_mesh(mesh, Path(out_glb))
    duration = time.perf_counter() - started
    LOGGER.info(
        "event=proxy_built glb=%s obj=%s faces=%s points=%s duration_s=%.3f",
        glb_path,
        obj_path,
        faces,
        prepared.points_filtered,
        duration,
    )
    return ProxyBuildResult(
        glb_path=glb_path,
        obj_path=obj_path,
        faces=faces,
        vertices=vertices,
        points_in=prepared.points_in,
        points_filtered=prepared.points_filtered,
        duration_s=duration,
    )


def _poisson_mesh(prepared: PreparedCloud, *, depth: int) -> tuple[object, object]:
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(list(prepared.points))
    pcd.normals = o3d.utility.Vector3dVector(list(prepared.normals))
    k_orient = min(DEFAULT_KNN_K, len(prepared.points))
    if k_orient >= 3:
        pcd.orient_normals_consistent_tangent_plane(k_orient)
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd,
        depth=depth,
    )
    if len(mesh.vertices) < 3 or len(mesh.triangles) < 1:
        raise empty_mesh("poisson returned no triangles")
    return mesh, densities


def _crop_low_density(
    mesh: object,
    densities: object,
    density_percentile: float,
) -> object:
    if densities is None or density_percentile <= 0.0:
        mesh.remove_degenerate_triangles()
        mesh.remove_unreferenced_vertices()
        mesh.compute_vertex_normals()
        return mesh
    values = np.asarray(densities)
    if values.size == 0:
        return mesh
    cutoff = float(np.quantile(values, density_percentile))
    mesh.remove_vertices_by_mask(values < cutoff)
    mesh.remove_degenerate_triangles()
    mesh.remove_unreferenced_vertices()
    if len(mesh.vertices) < 3 or len(mesh.triangles) < 1:
        raise no_faces_after_crop()
    mesh.compute_vertex_normals()
    return mesh


def _simplify(mesh: object, simplify_target: int) -> object:
    if simplify_target == 0 or len(mesh.triangles) <= simplify_target:
        return mesh
    simplified = mesh.simplify_quadric_decimation(
        target_number_of_triangles=simplify_target
    )
    simplified.compute_vertex_normals()
    return simplified


def _export_mesh(mesh: object, out_glb: Path) -> tuple[Path | None, Path | None]:
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    if _write_triangle_mesh(out_glb, mesh) and out_glb.is_file():
        return out_glb, None
    obj_path = out_glb.with_suffix(".obj")
    if _write_triangle_mesh(obj_path, mesh) and obj_path.is_file():
        LOGGER.info("event=proxy_glb_fallback obj=%s", obj_path)
        return None, obj_path
    raise export_failed(str(out_glb))


def _write_triangle_mesh(path: Path, mesh: object) -> bool:
    return bool(
        o3d.io.write_triangle_mesh(
            str(path),
            mesh,
            write_vertex_normals=True,
            write_vertex_colors=False,
            write_triangle_uvs=False,
        )
    )
