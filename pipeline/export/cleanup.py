"""Filter needle/floater Gaussians from a 3DGS / gsplat master PLY.

gsplat stores ``scale_*`` in log-space and ``opacity`` as a logit.
Needles (anisotropy of 10^5–10^12) survive training-view metrics but explode
in the orbit viewer. ``splat-transform --filter-floaters`` is the web path;
this runs in stdlib so export stays usable when that binary is missing.
"""

from __future__ import annotations

import logging
import math
import struct
from dataclasses import dataclass
from pathlib import Path

from export.config import ExportConfig

LOGGER = logging.getLogger("pipeline.export.cleanup")

_TYPE_STRUCT: dict[str, str] = {
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

_MIN_KEEP_ABS = 16
_MIN_KEEP_RATIO = 0.05
_LOG_SCALE_CLAMP = (-20.0, 4.0)


@dataclass(frozen=True, slots=True)
class CleanupStats:
    input_count: int
    kept: int
    dropped_aniso: int
    dropped_opacity: int
    dropped_scale: int
    clamped: int
    skipped: bool
    reason: str


def _robust_diag(xs: list[float], ys: list[float], zs: list[float], crop_quantile: float) -> float:
    """AABB diagonal; uses percentiles when crop is on so outliers do not inflate max scale."""
    if not xs:
        return 1.0
    if crop_quantile > 0:
        dx = _percentile(xs, 1.0 - crop_quantile) - _percentile(xs, crop_quantile)
        dy = _percentile(ys, 1.0 - crop_quantile) - _percentile(ys, crop_quantile)
        dz = _percentile(zs, 1.0 - crop_quantile) - _percentile(zs, crop_quantile)
        diag = math.sqrt(dx * dx + dy * dy + dz * dz)
    else:
        diag = math.sqrt(
            (max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2 + (max(zs) - min(zs)) ** 2
        )
    if not math.isfinite(diag) or diag <= 1e-8:
        return 1.0
    return diag


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * quantile))))
    return ordered[index]


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_v = math.exp(value)
    return exp_v / (1.0 + exp_v)


def _parse_header(blob: bytes) -> tuple[list[str], int, dict[str, int], int] | None:
    marker = b"end_header\n"
    split_at = blob.find(marker)
    if split_at < 0:
        marker = b"end_header\r\n"
        split_at = blob.find(marker)
    if split_at < 0:
        return None
    header_text = blob[: split_at + len(marker)].decode("ascii", errors="replace")
    lines = [line.strip() for line in header_text.splitlines() if line.strip()]
    if not lines or lines[0].lower() != "ply":
        return None
    fmt = ""
    count = 0
    props: list[tuple[str, str]] = []
    in_vertex = False
    for line in lines[1:]:
        tokens = line.split()
        if not tokens:
            continue
        kind = tokens[0].lower()
        if kind == "format":
            fmt = tokens[1].lower() if len(tokens) > 1 else ""
        elif kind == "element":
            in_vertex = len(tokens) >= 3 and tokens[1] == "vertex"
            if in_vertex:
                try:
                    count = int(tokens[2])
                except ValueError:
                    return None
        elif kind == "property" and in_vertex:
            if len(tokens) == 3 and tokens[1].lower() != "list":
                props.append((tokens[1].lower(), tokens[2]))
            else:
                return None
    if fmt != "binary_little_endian" or count < 1 or not props:
        return None
    names = [name for _typ, name in props]
    required = {"x", "y", "z", "scale_0", "scale_1", "scale_2", "opacity"}
    if not required.issubset(names):
        return None
    offsets: dict[str, int] = {}
    cursor = 0
    for typ, name in props:
        code = _TYPE_STRUCT.get(typ)
        if code is None:
            return None
        offsets[name] = cursor
        cursor += struct.calcsize(code)
    return lines, count, offsets, cursor


def _rewrite_header(lines: list[str], kept: int) -> bytes:
    out: list[str] = []
    wrote_comment = False
    for line in lines:
        if line.startswith("element vertex"):
            out.append(f"element vertex {kept}")
            continue
        if line == "end_header" and not wrote_comment:
            out.append("comment gs-cleanup needles/floaters")
            wrote_comment = True
        out.append(line)
    return ("\n".join(out) + "\n").encode("ascii")


def clean_gaussian_ply(path: Path, config: ExportConfig) -> CleanupStats:
    """Rewrite ``path`` in place. Invalid / unsafe PLYs are left untouched."""
    skipped = CleanupStats(0, 0, 0, 0, 0, 0, True, "skipped")
    if not config.cleanup_needles:
        return CleanupStats(0, 0, 0, 0, 0, 0, True, "disabled")
    try:
        blob = path.read_bytes()
    except OSError:
        return skipped
    parsed = _parse_header(blob)
    if parsed is None:
        return CleanupStats(0, 0, 0, 0, 0, 0, True, "unsupported")
    lines, count, offsets, rec_size = parsed
    marker = b"end_header\n"
    header_end = blob.find(marker)
    crlf = False
    if header_end < 0:
        marker = b"end_header\r\n"
        header_end = blob.find(marker)
        crlf = True
    payload = blob[header_end + len(marker) :]
    expected = rec_size * count
    if len(payload) < expected:
        return CleanupStats(count, 0, 0, 0, 0, 0, True, "truncated")

    unpack_f = struct.Struct("<f")
    pack_f = struct.Struct("<f")

    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    records: list[bytearray] = []
    for index in range(count):
        raw = bytearray(payload[index * rec_size : (index + 1) * rec_size])
        records.append(raw)
        xs.append(unpack_f.unpack_from(raw, offsets["x"])[0])
        ys.append(unpack_f.unpack_from(raw, offsets["y"])[0])
        zs.append(unpack_f.unpack_from(raw, offsets["z"])[0])

    diag = _robust_diag(xs, ys, zs, config.crop_quantile)
    max_lin_allowed = config.max_scale_frac * diag
    min_lin_allowed = config.min_scale_frac * diag

    kept_records: list[bytearray] = []
    dropped_aniso = 0
    dropped_opacity = 0
    dropped_scale = 0
    clamped = 0
    lo, hi = _LOG_SCALE_CLAMP

    for raw in records:
        s0 = unpack_f.unpack_from(raw, offsets["scale_0"])[0]
        s1 = unpack_f.unpack_from(raw, offsets["scale_1"])[0]
        s2 = unpack_f.unpack_from(raw, offsets["scale_2"])[0]
        opacity = unpack_f.unpack_from(raw, offsets["opacity"])[0]
        if _sigmoid(opacity) < config.min_opacity_sigmoid:
            dropped_opacity += 1
            continue
        lin = (math.exp(s0), math.exp(s1), math.exp(s2))
        max_lin = max(lin)
        if max_lin < min_lin_allowed:
            dropped_scale += 1
            continue
        changed = False
        if max_lin > max_lin_allowed:
            factor = max_lin_allowed / max_lin
            lin = (lin[0] * factor, lin[1] * factor, lin[2] * factor)
            max_lin = max_lin_allowed
            changed = True
        min_lin = min(lin)
        aniso = max_lin / max(min_lin, 1e-12)
        if config.max_anisotropy > 0 and aniso > config.max_anisotropy:
            dropped_aniso += 1
            continue
        if config.clamp_anisotropy > 0 and aniso > config.clamp_anisotropy:
            min_allowed = max_lin / config.clamp_anisotropy
            lin = (max(lin[0], min_allowed), max(lin[1], min_allowed), max(lin[2], min_allowed))
            changed = True
        if changed:
            pack_f.pack_into(raw, offsets["scale_0"], min(hi, max(lo, math.log(max(lin[0], 1e-12)))))
            pack_f.pack_into(raw, offsets["scale_1"], min(hi, max(lo, math.log(max(lin[1], 1e-12)))))
            pack_f.pack_into(raw, offsets["scale_2"], min(hi, max(lo, math.log(max(lin[2], 1e-12)))))
            clamped += 1
        kept_records.append(raw)

    if config.crop_quantile > 0 and kept_records:
        kxs = [unpack_f.unpack_from(raw, offsets["x"])[0] for raw in kept_records]
        kys = [unpack_f.unpack_from(raw, offsets["y"])[0] for raw in kept_records]
        kzs = [unpack_f.unpack_from(raw, offsets["z"])[0] for raw in kept_records]
        q = config.crop_quantile
        lo_x, hi_x = _percentile(kxs, q), _percentile(kxs, 1.0 - q)
        lo_y, hi_y = _percentile(kys, q), _percentile(kys, 1.0 - q)
        lo_z, hi_z = _percentile(kzs, q), _percentile(kzs, 1.0 - q)
        pad_x = (hi_x - lo_x) * 0.05
        pad_y = (hi_y - lo_y) * 0.05
        pad_z = (hi_z - lo_z) * 0.05
        cropped: list[bytearray] = []
        for raw, x, y, z in zip(kept_records, kxs, kys, kzs, strict=True):
            if x < lo_x - pad_x or x > hi_x + pad_x:
                dropped_scale += 1
                continue
            if y < lo_y - pad_y or y > hi_y + pad_y:
                dropped_scale += 1
                continue
            if z < lo_z - pad_z or z > hi_z + pad_z:
                dropped_scale += 1
                continue
            cropped.append(raw)
        kept_records = cropped

    kept = len(kept_records)
    min_keep = max(_MIN_KEEP_ABS, int(count * _MIN_KEEP_RATIO))
    if kept < min_keep:
        LOGGER.warning(
            "event=ply_cleanup_fallback_clamp input=%s kept=%s min_keep=%s",
            count,
            kept,
            min_keep,
        )
        kept_records = []
        dropped_aniso = 0
        dropped_opacity = 0
        dropped_scale = 0
        clamped = 0
        for raw in records:
            s0 = unpack_f.unpack_from(raw, offsets["scale_0"])[0]
            s1 = unpack_f.unpack_from(raw, offsets["scale_1"])[0]
            s2 = unpack_f.unpack_from(raw, offsets["scale_2"])[0]
            lin = (math.exp(s0), math.exp(s1), math.exp(s2))
            max_lin = max(lin)
            changed = False
            if max_lin > max_lin_allowed:
                factor = max_lin_allowed / max(max_lin, 1e-12)
                lin = (lin[0] * factor, lin[1] * factor, lin[2] * factor)
                max_lin = max_lin_allowed
                changed = True
            min_lin = min(lin)
            aniso = max_lin / max(min_lin, 1e-12)
            if config.clamp_anisotropy > 0 and aniso > config.clamp_anisotropy:
                min_allowed = max_lin / config.clamp_anisotropy
                lin = (
                    max(lin[0], min_allowed),
                    max(lin[1], min_allowed),
                    max(lin[2], min_allowed),
                )
                changed = True
            if changed:
                pack_f.pack_into(
                    raw, offsets["scale_0"], min(hi, max(lo, math.log(max(lin[0], 1e-12))))
                )
                pack_f.pack_into(
                    raw, offsets["scale_1"], min(hi, max(lo, math.log(max(lin[1], 1e-12))))
                )
                pack_f.pack_into(
                    raw, offsets["scale_2"], min(hi, max(lo, math.log(max(lin[2], 1e-12))))
                )
                clamped += 1
            kept_records.append(raw)
        kept = len(kept_records)

    header = _rewrite_header(lines, kept)
    if crlf:
        header = header.replace(b"\n", b"\r\n")
    tmp = path.with_suffix(path.suffix + ".clean.tmp")
    tmp.write_bytes(header + b"".join(kept_records))
    tmp.replace(path)
    LOGGER.info(
        "event=ply_cleanup input=%s kept=%s aniso=%s opacity=%s scale=%s clamped=%s",
        count,
        kept,
        dropped_aniso,
        dropped_opacity,
        dropped_scale,
        clamped,
    )
    return CleanupStats(
        count, kept, dropped_aniso, dropped_opacity, dropped_scale, clamped, False, "ok"
    )
