"""Job-stage contract: metrics dict, ply resolution, mapping context."""

from __future__ import annotations

from pathlib import Path

import pytest
from pipeline.meshproxy import (
    AVAILABLE,
    BackendUnavailableError,
    MeshProxyError,
    meshproxy_stage,
)
from pipeline.meshproxy.reconstruct import ProxyBuildResult
from pipeline.meshproxy.stage import (
    MeshProxyContext,
    make_stage_result,
    resolve_master_ply,
)
from ply_fixtures import grid_points, write_binary_ply


def test_make_stage_result_metrics_schema() -> None:
    payload = make_stage_result(
        ProxyBuildResult(
            glb_path=Path("export/proxy.glb"),
            obj_path=None,
            faces=1200,
            vertices=800,
            points_in=5000,
            points_filtered=4200,
            duration_s=1.25,
        )
    )
    assert set(payload["metrics"]) == {
        "points_in",
        "points_filtered",
        "faces",
        "duration_s",
    }
    assert payload["metrics"]["points_in"] == 5000
    assert payload["metrics"]["points_filtered"] == 4200
    assert payload["metrics"]["faces"] == 1200
    assert payload["metrics"]["duration_s"] == pytest.approx(1.25)
    assert Path(payload["artifacts"]["proxy_glb"]) == Path("export/proxy.glb")
    assert "proxy_obj" not in payload["artifacts"]
    assert "Malha proxy" in payload["message"]


def test_resolve_master_ply_prefers_export_layout(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    master = write_binary_ply(
        export_dir / "master.ply",
        points=grid_points(2, 2, 2),
    )
    train = tmp_path / "train" / "ply"
    train.mkdir(parents=True)
    write_binary_ply(train / "point_cloud_0000.ply", points=grid_points(2, 2, 1))
    found = resolve_master_ply(MeshProxyContext(work_dir=tmp_path))
    assert found == master


def test_resolve_master_ply_falls_back_to_train(tmp_path: Path) -> None:
    train = tmp_path / "train" / "ply"
    train.mkdir(parents=True)
    write_binary_ply(train / "point_cloud_0001.ply", points=[(0.0, 0.0, 0.0)])
    newer = write_binary_ply(train / "point_cloud_0010.ply", points=[(1.0, 0.0, 0.0)])
    found = resolve_master_ply(MeshProxyContext(work_dir=tmp_path))
    assert found == newer


def test_resolve_master_ply_prefers_step_29999_over_lexical_6999(tmp_path: Path) -> None:
    train = tmp_path / "train" / "ply"
    train.mkdir(parents=True)
    write_binary_ply(train / "point_cloud_6999.ply", points=[(0.0, 0.0, 0.0)])
    newest = write_binary_ply(train / "point_cloud_29999.ply", points=[(1.0, 0.0, 0.0)])
    found = resolve_master_ply(MeshProxyContext(work_dir=tmp_path))
    assert found == newest


def test_missing_ply_is_explained(tmp_path: Path) -> None:
    with pytest.raises(MeshProxyError) as caught:
        meshproxy_stage(MeshProxyContext(work_dir=tmp_path, min_points=1))
    assert caught.value.code == "MISSING_PLY"
    assert "ply" in caught.value.user_message.lower()


def test_stage_accepts_mapping_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    write_binary_ply(
        export_dir / "master.ply",
        points=[(0.0, 0.0, 0.0)],
    )
    monkeypatch.setattr("pipeline.meshproxy.stage.AVAILABLE", True)
    with pytest.raises(MeshProxyError) as caught:
        meshproxy_stage({"work_dir": tmp_path, "min_points": 80})
    assert caught.value.code == "SPARSE_CLOUD"


def test_stage_metrics_via_monkeypatched_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    write_binary_ply(export_dir / "master.ply", points=grid_points(3, 3, 3))
    fake = ProxyBuildResult(
        glb_path=export_dir / "proxy.glb",
        obj_path=None,
        faces=42,
        vertices=30,
        points_in=27,
        points_filtered=24,
        duration_s=0.4,
    )

    def _fake_build(*_args: object, **_kwargs: object) -> ProxyBuildResult:
        return fake

    monkeypatch.setattr("pipeline.meshproxy.stage.AVAILABLE", True)
    monkeypatch.setattr("pipeline.meshproxy.stage.build_proxy", _fake_build)
    progress: list[tuple[float, str]] = []

    def _on_progress(fraction: float, message: str) -> None:
        progress.append((fraction, message))

    result = meshproxy_stage(
        MeshProxyContext(work_dir=tmp_path, progress=_on_progress)
    )
    assert result["metrics"]["faces"] == 42
    assert result["metrics"]["points_in"] == 27
    assert result["metrics"]["points_filtered"] == 24
    assert result["artifacts"]["proxy_glb"].endswith("proxy.glb")
    assert progress
    assert progress[-1][0] == pytest.approx(1.0)


def test_stage_without_open3d_on_dense_cloud(tmp_path: Path) -> None:
    if AVAILABLE:
        pytest.skip("Open3D is installed in this environment")
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    write_binary_ply(
        export_dir / "master.ply",
        points=grid_points(5, 5, 5),
        opacities=[2.0] * 125,
    )
    with pytest.raises(BackendUnavailableError) as caught:
        meshproxy_stage(
            MeshProxyContext(work_dir=tmp_path, min_points=10, density_percentile=0.0)
        )
    assert caught.value.code == "OPEN3D_UNAVAILABLE"


def test_stage_rejects_huge_cloud_from_header_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    write_binary_ply(
        export_dir / "master.ply",
        points=grid_points(2, 2, 2),
        opacities=[2.0] * 8,
    )
    monkeypatch.setattr("pipeline.meshproxy.stage.AVAILABLE", True)
    monkeypatch.setattr("pipeline.meshproxy.stage.MAX_MESHPROXY_VERTICES", 3)
    with pytest.raises(MeshProxyError) as caught:
        meshproxy_stage(MeshProxyContext(work_dir=tmp_path, min_points=1))
    assert caught.value.code == "MESHPROXY_TOO_LARGE"
