"""Stdlib parser for 3DGS / gsplat Gaussian ``.ply`` files.

Does **not** import Open3D or NumPy. Header is always ASCII; vertex payload
is ``binary_little_endian`` (3DGS default) or ASCII. ``struct`` unpacks
little-endian scalars.

Assumed 3DGS / INRIA / gsplat vertex fields
-------------------------------------------
Required:

* ``x``, ``y``, ``z`` — Gaussian centres (float32).

Optional, consumed:

* ``nx``, ``ny``, ``nz`` — normals (float32). Classic 3DGS writes zeros;
  the reconstruction path re-estimates when they are unusable.
* ``opacity`` — **logit** (inverse sigmoid). Activated with
  ``sigmoid(opacity)`` at filter time. ``alpha`` is accepted as an alias.

Ignored but tolerated (SH / covariance of the official exporter):

* ``f_dc_0..2``, ``f_rest_*``, ``scale_0..2``, ``rot_0..3``
* ``red``, ``green``, ``blue`` (uchar preview colours)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO

from .errors import assert_never, invalid_ply, unsupported_ply
from .types import Vec3

_TYPE_TO_STRUCT: dict[str, str] = {
    "char": "b",
    "int8": "b",
    "uchar": "B",
    "uint8": "B",
    "short": "h",
    "int16": "h",
    "ushort": "H",
    "uint16": "H",
    "int": "i",
    "int32": "i",
    "uint": "I",
    "uint32": "I",
    "float": "f",
    "float32": "f",
    "double": "d",
    "float64": "d",
}

_TYPE_TO_SIZE: dict[str, int] = {
    name: struct.calcsize(code) for name, code in _TYPE_TO_STRUCT.items()
}


class PlyFormat(StrEnum):
    ASCII = "ascii"
    BINARY_LE = "binary_little_endian"
    BINARY_BE = "binary_big_endian"


@dataclass(frozen=True, slots=True)
class PlyProperty:
    name: str
    type_name: str
    is_list: bool
    count_type: str | None


@dataclass(frozen=True, slots=True)
class PlyElement:
    name: str
    count: int
    properties: tuple[PlyProperty, ...]


@dataclass(frozen=True, slots=True)
class PlyHeader:
    ply_format: PlyFormat
    elements: tuple[PlyElement, ...]
    comments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GaussianCloud:
    """Centres (+ optional normals / raw opacity logits) from a 3DGS PLY."""

    points: tuple[Vec3, ...]
    normals: tuple[Vec3, ...] | None
    opacities: tuple[float, ...] | None
    property_names: tuple[str, ...]
    ply_format: PlyFormat
    comments: tuple[str, ...] = ()

    @property
    def vertex_count(self) -> int:
        return len(self.points)


def read_gaussian_ply(path: str | Path) -> GaussianCloud:
    """Parse a 3DGS-style PLY and return Gaussian centres."""
    ply_path = Path(path)
    try:
        with ply_path.open("rb") as handle:
            header = _parse_header(_read_header_lines(handle))
            return _read_vertices(handle, header)
    except OSError as exc:
        raise invalid_ply(str(ply_path)) from exc


def _read_header_lines(handle: BinaryIO) -> list[str]:
    lines: list[str] = []
    while True:
        raw = handle.readline()
        if not raw:
            raise invalid_ply("unexpected EOF in PLY header")
        line = raw.decode("ascii", errors="replace").strip()
        if not line:
            continue
        lines.append(line)
        if line.lower() == "end_header":
            return lines


def _parse_header(lines: list[str]) -> PlyHeader:
    if not lines or lines[0].lower() != "ply":
        raise invalid_ply("missing ply magic")

    ply_format: PlyFormat | None = None
    comments: list[str] = []
    elements: list[PlyElement] = []
    current_name: str | None = None
    current_count: int = 0
    current_props: list[PlyProperty] = []

    def flush() -> None:
        nonlocal current_name, current_count, current_props
        if current_name is None:
            return
        elements.append(
            PlyElement(current_name, current_count, tuple(current_props))
        )
        current_name = None
        current_count = 0
        current_props = []

    for line in lines[1:]:
        lowered = line.lower()
        if lowered == "end_header":
            flush()
            break
        tokens = line.split()
        if not tokens:
            continue
        kind = tokens[0].lower()
        if kind == "format":
            ply_format = _parse_format(tokens)
            continue
        if kind == "comment":
            comments.append(line[8:].strip() if len(line) > 8 else "")
            continue
        if kind == "obj_info":
            continue
        if kind == "element":
            flush()
            if len(tokens) < 3:
                raise invalid_ply(f"malformed element: {line}")
            current_name = tokens[1]
            try:
                current_count = int(tokens[2])
            except ValueError as exc:
                raise invalid_ply(f"bad element count: {line}") from exc
            current_props = []
            continue
        if kind == "property":
            if current_name is None:
                raise invalid_ply("property before element")
            current_props.append(_parse_property(tokens))
            continue

    if ply_format is None:
        raise invalid_ply("missing format line")
    if not elements:
        raise invalid_ply("no elements in header")
    return PlyHeader(ply_format, tuple(elements), tuple(comments))


def _parse_format(tokens: list[str]) -> PlyFormat:
    if len(tokens) < 2:
        raise invalid_ply("malformed format line")
    name = tokens[1].lower()
    for candidate in PlyFormat:
        if candidate.value == name:
            return candidate
    raise unsupported_ply(f"unknown format {tokens[1]!r}")


def _parse_property(tokens: list[str]) -> PlyProperty:
    # property <type> <name>
    # property list <count_type> <item_type> <name>
    if len(tokens) < 3:
        raise invalid_ply(f"malformed property: {' '.join(tokens)}")
    if tokens[1].lower() == "list":
        if len(tokens) < 5:
            raise invalid_ply(f"malformed list property: {' '.join(tokens)}")
        count_type = tokens[2].lower()
        item_type = tokens[3].lower()
        name = tokens[4]
        _require_type(count_type)
        _require_type(item_type)
        return PlyProperty(name, item_type, True, count_type)
    type_name = tokens[1].lower()
    _require_type(type_name)
    return PlyProperty(tokens[2], type_name, False, None)


def _require_type(type_name: str) -> None:
    if type_name not in _TYPE_TO_STRUCT:
        raise unsupported_ply(f"unknown PLY type {type_name!r}")


def _read_vertices(handle: BinaryIO, header: PlyHeader) -> GaussianCloud:
    vertex = next((item for item in header.elements if item.name == "vertex"), None)
    if vertex is None:
        raise invalid_ply("no vertex element")

    for element in header.elements:
        if element is vertex:
            rows = _read_element_rows(handle, element, header.ply_format)
            return _cloud_from_rows(rows, vertex, header)
        _skip_element(handle, element, header.ply_format)

    raise invalid_ply("vertex element not reached")


def _cloud_from_rows(
    rows: list[dict[str, float]],
    vertex: PlyElement,
    header: PlyHeader,
) -> GaussianCloud:
    names = tuple(prop.name for prop in vertex.properties)
    if "x" not in names or "y" not in names or "z" not in names:
        raise invalid_ply("vertex element missing x, y or z")

    points: list[Vec3] = []
    normals_acc: list[Vec3] = []
    opacities_acc: list[float] = []
    has_normals = {"nx", "ny", "nz"}.issubset(names)
    opacity_name = "opacity" if "opacity" in names else ("alpha" if "alpha" in names else None)

    for row in rows:
        points.append((float(row["x"]), float(row["y"]), float(row["z"])))
        if has_normals:
            normals_acc.append((float(row["nx"]), float(row["ny"]), float(row["nz"])))
        if opacity_name is not None:
            opacities_acc.append(float(row[opacity_name]))

    return GaussianCloud(
        points=tuple(points),
        normals=tuple(normals_acc) if has_normals else None,
        opacities=tuple(opacities_acc) if opacity_name is not None else None,
        property_names=names,
        ply_format=header.ply_format,
        comments=header.comments,
    )


def _read_element_rows(
    handle: BinaryIO,
    element: PlyElement,
    ply_format: PlyFormat,
) -> list[dict[str, float]]:
    match ply_format:
        case PlyFormat.BINARY_LE:
            return _read_binary_rows(handle, element, "<")
        case PlyFormat.ASCII:
            return _read_ascii_rows(handle, element)
        case PlyFormat.BINARY_BE:
            raise unsupported_ply("binary_big_endian")
        case _:
            return assert_never(ply_format)


def _skip_element(handle: BinaryIO, element: PlyElement, ply_format: PlyFormat) -> None:
    match ply_format:
        case PlyFormat.BINARY_LE:
            _read_binary_rows(handle, element, "<")
        case PlyFormat.ASCII:
            _read_ascii_rows(handle, element)
        case PlyFormat.BINARY_BE:
            raise unsupported_ply("binary_big_endian")
        case _:
            assert_never(ply_format)


def _fixed_struct(element: PlyElement, endian: str) -> struct.Struct | None:
    if any(prop.is_list for prop in element.properties):
        return None
    fmt = endian + "".join(_TYPE_TO_STRUCT[prop.type_name] for prop in element.properties)
    return struct.Struct(fmt)


def _read_binary_rows(
    handle: BinaryIO,
    element: PlyElement,
    endian: str,
) -> list[dict[str, float]]:
    names = [prop.name for prop in element.properties]
    fixed = _fixed_struct(element, endian)
    rows: list[dict[str, float]] = []
    if fixed is not None:
        blob = handle.read(fixed.size * element.count)
        if len(blob) != fixed.size * element.count:
            raise invalid_ply("truncated binary vertex payload")
        for index in range(element.count):
            values = fixed.unpack_from(blob, index * fixed.size)
            rows.append(
                {name: float(value) for name, value in zip(names, values, strict=True)}
            )
        return rows

    for _ in range(element.count):
        rows.append(_read_binary_variable_row(handle, element, endian))
    return rows


def _read_binary_variable_row(
    handle: BinaryIO,
    element: PlyElement,
    endian: str,
) -> dict[str, float]:
    row: dict[str, float] = {}
    for prop in element.properties:
        if not prop.is_list:
            row[prop.name] = _unpack_scalar(handle, endian, prop.type_name)
            continue
        assert prop.count_type is not None
        count = int(_unpack_scalar(handle, endian, prop.count_type))
        items = [_unpack_scalar(handle, endian, prop.type_name) for _ in range(count)]
        row[prop.name] = float(items[0]) if items else 0.0
    return row


def _unpack_scalar(handle: BinaryIO, endian: str, type_name: str) -> float:
    code = _TYPE_TO_STRUCT[type_name]
    size = _TYPE_TO_SIZE[type_name]
    blob = handle.read(size)
    if len(blob) != size:
        raise invalid_ply("truncated binary scalar")
    value = struct.unpack(f"{endian}{code}", blob)[0]
    return float(value)


def _read_ascii_rows(handle: BinaryIO, element: PlyElement) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    remaining = element.count
    while remaining > 0:
        raw = handle.readline()
        if not raw:
            raise invalid_ply("truncated ASCII vertex payload")
        line = raw.decode("ascii", errors="replace").strip()
        if not line or line.startswith("comment"):
            continue
        tokens = line.split()
        rows.append(_ascii_row(tokens, element.properties))
        remaining -= 1
    return rows


def _ascii_row(tokens: list[str], properties: tuple[PlyProperty, ...]) -> dict[str, float]:
    row: dict[str, float] = {}
    cursor = 0
    try:
        for prop in properties:
            if not prop.is_list:
                row[prop.name] = float(tokens[cursor])
                cursor += 1
                continue
            count = int(tokens[cursor])
            cursor += 1
            items = [float(tokens[cursor + offset]) for offset in range(count)]
            cursor += count
            row[prop.name] = items[0] if items else 0.0
    except (IndexError, ValueError) as exc:
        raise invalid_ply("malformed ASCII vertex") from exc
    return row
