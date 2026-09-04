"""Quality gate and Open3D-gated reconstruction."""

from __future__ import annotations

from pathlib import Path

import pytest
from pipeline.meshproxy import AVAILABLE, SparseCloudError, build_proxy
from pipeline.meshproxy.reconstruct import prepare_cloud
from ply_fixtures import grid_points, write_binary_ply


def test_prepare_cloud_rejects_sparse_after_filter(tmp_path: Path) -> None:
    path = write_binary_ply(
        tmp_path / "tiny.ply",
        points=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        opacities=[2.0, 2.0, 2.0],
    )
    with pytest.raises(SparseCloudError) as caught:
        prepare_cloud(
            path,
            min_points=20,
            knn_k=2,
            density_percentile=0.0,
            opacity_threshold=0.0,
        )
    assert caught.value.code == "SPARSE_CLOUD"
    assert "esparsa" in caught.value.user_message
    assert "20" in caught.value.user_message
    assert "3" in caught.value.user_message


def test_build_proxy_sparse_gate_runs_without_open3d(tmp_path: Path) -> None:
    path = write_binary_ply(
        tmp_path / "few.ply",
        points=[(0.0, 0.0, 0.0), (0.5, 0.0, 0.0)],
    )
    with pytest.raises(SparseCloudError) as caught:
        build_proxy(
            path,
            tmp_path / "proxy.glb",
            min_points=50,
            density_percentile=0.0,
            knn_k=1,
        )
    assert caught.value.code == "SPARSE_CLOUD"


def test_prepare_cloud_keeps_a_dense_grid(tmp_path: Path) -> None:
    path = write_binary_ply(
        tmp_path / "grid.ply",
        points=grid_points(6, 6, 4),
        opacities=[2.0] * (6 * 6 * 4),
    )
    prepared = prepare_cloud(
        path,
        min_points=50,
        knn_k=8,
        density_percentile=0.0,
        opacity_threshold=0.01,
    )
    assert prepared.points_in == 144
    assert prepared.points_filtered >= 50
    assert len(prepared.normals) == prepared.points_filtered
    length = sum(component * component for component in prepared.normals[0])
    assert length == pytest.approx(1.0, abs=0.2)


def test_prepare_cloud_ignores_zero_ply_normals(tmp_path: Path) -> None:
    points = grid_points(4, 4, 4)
    zeros = [(0.0, 0.0, 0.0)] * len(points)
    path = write_binary_ply(
        tmp_path / "zeros_n.ply",
        points=points,
        normals=zeros,
    )
    prepared = prepare_cloud(
        path,
        min_points=20,
        knn_k=8,
        density_percentile=0.0,
        opacity_threshold=0.0,
    )
    assert any(
        nx * nx + ny * ny + nz * nz > 0.25
        for nx, ny, nz in prepared.normals
    )


@pytest.mark.skipif(not AVAILABLE, reason="Open3D not installed")
def test_build_proxy_writes_mesh_when_open3d_present(tmp_path: Path) -> None:
    path = write_binary_ply(
        tmp_path / "sphereish.ply",
        points=grid_points(8, 8, 8),
        opacities=[2.0] * (8 * 8 * 8),
    )
    out = tmp_path / "export" / "proxy.glb"
    result = build_proxy(
        path,
        out,
        depth=5,
        simplify_target=2_000,
        density_percentile=0.05,
        min_points=50,
        knn_k=8,
    )
    assert result.faces >= 1
    assert result.points_in == 512
    assert result.duration_s >= 0.0
    assert result.method == "poisson"
    written = result.glb_path or result.obj_path
    assert written is not None
    assert written.is_file()
