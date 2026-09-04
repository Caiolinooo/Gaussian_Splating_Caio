"""ffprobe command builder and JSON parser."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ingest.config import VideoProbe
from ingest.errors import video_unreadable


def build_ffprobe_command(ffprobe: str, source: Path) -> list[str]:
    return [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,duration,r_frame_rate,nb_frames",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(source),
    ]


def _parse_fraction(value: str | None) -> float | None:
    if not value:
        return None
    if "/" in value:
        num_s, den_s = value.split("/", 1)
        try:
            num = float(num_s)
            den = float(den_s)
        except ValueError:
            return None
        if den == 0:
            return None
        return num / den
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def parse_ffprobe_json(payload: dict[str, Any], *, source: Path) -> VideoProbe:
    streams = payload.get("streams")
    if not isinstance(streams, list) or not streams:
        raise video_unreadable(str(source), "no video stream")
    stream = streams[0]
    if not isinstance(stream, dict):
        raise video_unreadable(str(source), "malformed stream")

    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    if width < 1 or height < 1:
        raise video_unreadable(str(source), "missing width/height")

    duration = _as_float(stream.get("duration"))
    if duration is None:
        fmt = payload.get("format")
        if isinstance(fmt, dict):
            duration = _as_float(fmt.get("duration"))
    if duration is None:
        raise video_unreadable(str(source), "missing duration")

    fps = _parse_fraction(str(stream.get("r_frame_rate") or ""))
    if fps is None:
        raise video_unreadable(str(source), "missing r_frame_rate")

    nb_raw = stream.get("nb_frames")
    nb_frames: int | None
    try:
        nb_frames = int(nb_raw) if nb_raw not in (None, "N/A", "") else None
    except (TypeError, ValueError):
        nb_frames = None

    return VideoProbe(
        path=source,
        width=width,
        height=height,
        duration_s=duration,
        fps=fps,
        nb_frames=nb_frames,
    )
