"""Upload payloads and tiny JWT helpers for API tests."""

from __future__ import annotations

import time
from typing import Any

from app.core.jwtutil import encode_hs256
from tests.conftest import TEST_JWT_SECRET


def bearer(user_id: str, *, secret: str = TEST_JWT_SECRET, exp_in: int = 3600) -> dict[str, str]:
    token = encode_hs256({"sub": user_id, "role": "authenticated", "exp": int(time.time()) + exp_in}, secret)
    return {"Authorization": f"Bearer {token}"}


def video_files(name: str = "walk.mp4", content: bytes = b"fake-mp4") -> dict[str, Any]:
    return {"file": (name, content, "video/mp4")}


def gif_files(name: str = "loop.gif", content: bytes = b"fake-gif") -> dict[str, Any]:
    return {"file": (name, content, "image/gif")}


def ply_files(name: str = "scan.ply", content: bytes = b"ply\nformat ascii 1.0\nend_header\n") -> dict[str, Any]:
    return {"file": (name, content, "application/octet-stream")}


def image_files(count: int, *, field: str = "files[]") -> list[tuple[str, tuple[str, bytes, str]]]:
    return [(field, (f"frame_{index:03d}.jpg", b"fake-jpg", "image/jpeg")) for index in range(count)]


def job_form(*, height: str = "1.75", key: str = "idem-1") -> dict[str, str]:
    return {"user_height_m": height, "idempotency_key": key}
