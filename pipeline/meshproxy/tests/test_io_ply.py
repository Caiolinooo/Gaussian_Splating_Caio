"""PLY parser: synthetic binary little-endian 3DGS-like files."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from pipeline.meshproxy.errors import MeshProxyError
from pipeline.meshproxy.io_ply import PlyFormat, read_gaussian_ply
from ply_fixtures import write_binary_ply


def test_reads_centres_and_opacity_logits(tmp_path: Path) -> None:
    points = [(0.0, 1.0, 2.0), (3.5, -4.0, 0.25)]
    opacities = [-2.0, 1.5]
    path = write_binary_ply(
        tmp_path / "gaussians.ply",
        points=points,
        opacities=opacities,
        extra_dc=True,
    )
    cloud = read_gaussian_ply(path)
    assert cloud.vertex_count == 2
    assert cloud.points[0] == pytest.approx(points[0])
    assert cloud.points[1] == pytest.approx(points[1])
    assert cloud.opacities is not None
    assert cloud.opacities[0] == pytest.approx(-2.0)
    assert cloud.opacities[1] == pytest.approx(1.5)
    assert cloud.normals is None
    assert cloud.ply_format is PlyFormat.BINARY_LE
    assert "f_dc_0" in cloud.property_names
    assert "opacity" in cloud.property_names


def test_reads_normals_when_present(tmp_path: Path) -> None:
    points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    normals = [(0.0, 0.0, 1.0), (0.0, 1.0, 0.0)]
    path = write_binary_ply(
        tmp_path / "with_n.ply",
        points=points,
        normals=normals,
    )
    cloud = read_gaussian_ply(path)
    assert cloud.normals is not None
    assert cloud.normals[0] == pytest.approx(normals[0])
    assert cloud.normals[1] == pytest.approx(normals[1])


def test_crlf_header_is_accepted(tmp_path: Path) -> None:
    header = (
        "ply\r\n"
        "format binary_little_endian 1.0\r\n"
        "element vertex 1\r\n"
        "property float x\r\n"
        "property float y\r\n"
        "property float z\r\n"
        "end_header\r\n"
    )
    path = tmp_path / "crlf.ply"
    path.write_bytes(header.encode("ascii") + struct.pack("<fff", 9.0, 8.0, 7.0))
    cloud = read_gaussian_ply(path)
    assert cloud.points[0] == pytest.approx((9.0, 8.0, 7.0))


def test_ascii_ply_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "ascii.ply"
    path.write_text(
        "ply\n"
        "format ascii 1.0\n"
        "element vertex 1\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property float opacity\n"
        "end_header\n"
        "1.25 2.5 -3 0.0\n",
        encoding="ascii",
    )
    cloud = read_gaussian_ply(path)
    assert cloud.ply_format is PlyFormat.ASCII
    assert cloud.points[0] == pytest.approx((1.25, 2.5, -3.0))
    assert cloud.opacities == pytest.approx((0.0,))


def test_missing_xyz_is_invalid(tmp_path: Path) -> None:
    path = tmp_path / "no_xyz.ply"
    path.write_text(
        "ply\n"
        "format ascii 1.0\n"
        "element vertex 1\n"
        "property float opacity\n"
        "end_header\n"
        "0.5\n",
        encoding="ascii",
    )
    with pytest.raises(MeshProxyError) as caught:
        read_gaussian_ply(path)
    assert caught.value.code == "INVALID_PLY"
    assert "x, y, z" in caught.value.user_message.lower() or "válido" in (
        caught.value.user_message.lower()
    )


def test_truncated_binary_payload(tmp_path: Path) -> None:
    path = tmp_path / "short.ply"
    path.write_bytes(
        b"ply\nformat binary_little_endian 1.0\n"
        b"element vertex 2\n"
        b"property float x\nproperty float y\nproperty float z\n"
        b"end_header\n" + struct.pack("<fff", 0.0, 0.0, 0.0)
    )
    with pytest.raises(MeshProxyError) as caught:
        read_gaussian_ply(path)
    assert caught.value.code == "INVALID_PLY"


def test_big_endian_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "be.ply"
    path.write_text(
        "ply\n"
        "format binary_big_endian 1.0\n"
        "element vertex 0\n"
        "property float x\nproperty float y\nproperty float z\n"
        "end_header\n",
        encoding="ascii",
    )
    with pytest.raises(MeshProxyError) as caught:
        read_gaussian_ply(path)
    assert caught.value.code == "UNSUPPORTED_PLY"
    assert "little-endian" in caught.value.user_message
