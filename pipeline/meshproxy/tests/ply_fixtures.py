"""Minimal 3DGS-like binary PLY writer (stdlib ``struct`` only)."""

from __future__ import annotations

import struct
from pathlib import Path


def write_binary_ply(
    path: Path,
    *,
    points: list[tuple[float, float, float]],
    normals: list[tuple[float, float, float]] | None = None,
    opacities: list[float] | None = None,
    extra_dc: bool = False,
) -> Path:
    """Write a ``binary_little_endian`` vertex-only PLY."""
    count = len(points)
    props = ["property float x", "property float y", "property float z"]
    if normals is not None:
        props.extend(
            ["property float nx", "property float ny", "property float nz"]
        )
    if extra_dc:
        props.extend(
            [
                "property float f_dc_0",
                "property float f_dc_1",
                "property float f_dc_2",
            ]
        )
    if opacities is not None:
        props.append("property float opacity")
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        "comment synthetic 3DGS-like splat\n"
        f"element vertex {count}\n"
        + "\n".join(props)
        + "\nend_header\n"
    )
    body = bytearray()
    for index, (x, y, z) in enumerate(points):
        body += struct.pack("<fff", x, y, z)
        if normals is not None:
            body += struct.pack("<fff", *normals[index])
        if extra_dc:
            body += struct.pack("<fff", 0.0, 0.0, 0.0)
        if opacities is not None:
            body += struct.pack("<f", opacities[index])
    path.write_bytes(header.encode("ascii") + bytes(body))
    return path


def grid_points(
    nx: int,
    ny: int,
    nz: int,
    *,
    spacing: float = 1.0,
) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                points.append((ix * spacing, iy * spacing, iz * spacing))
    return points
