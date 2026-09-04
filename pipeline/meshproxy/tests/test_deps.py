"""Optional extras must not break import; execution raises when missing."""

from __future__ import annotations

import sys

import pytest
from pipeline.meshproxy import AVAILABLE, BackendUnavailableError, build_proxy
from pipeline.meshproxy._deps import np, o3d
from ply_fixtures import grid_points, write_binary_ply


def test_available_flag_is_boolean() -> None:
    assert AVAILABLE in {True, False}


def test_package_import_does_not_require_open3d() -> None:
    import pipeline.meshproxy as meshproxy

    assert meshproxy.AVAILABLE is AVAILABLE
    if not AVAILABLE:
        assert o3d is None
        assert np is None
        assert sys.modules.get("open3d") in {None}


def test_build_proxy_raises_when_open3d_missing(tmp_path) -> None:
    if AVAILABLE:
        pytest.skip("Open3D is installed in this environment")
    ply = write_binary_ply(tmp_path / "dense.ply", points=grid_points(5, 5, 5))
    with pytest.raises(BackendUnavailableError, match="Open3D") as caught:
        build_proxy(ply, tmp_path / "proxy.glb", min_points=10)
    assert caught.value.code == "OPEN3D_UNAVAILABLE"
    assert "Open3D" in caught.value.user_message
