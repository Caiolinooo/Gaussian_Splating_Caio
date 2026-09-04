"""Validate and persist multipart uploads under ``{DATA_ROOT}/{user}/{job}/uploads``."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import unprocessable

LOGGER = logging.getLogger("gs.api.upload")

VIDEO_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"})
IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".heic", ".heif"})
MIN_HEIGHT_M = 0.5
MAX_HEIGHT_M = 2.8


@dataclass(frozen=True)
class SavedUpload:
    source_kind: str
    paths: tuple[Path, ...]
    original_names: tuple[str, ...]


def safe_filename(name: str | None, fallback: str) -> str:
    raw = Path(name or fallback).name
    if not raw or raw in {".", ".."}:
        return fallback
    return raw


def suffix_of(name: str) -> str:
    return Path(name).suffix.lower()


def parse_user_height_m(raw: str) -> float:
    normalized = raw.strip().replace(",", ".")
    try:
        value = float(normalized)
    except ValueError as exc:
        raise unprocessable("A altura informada é inválida.", "INVALID_HEIGHT") from exc
    if value <= 0:
        raise unprocessable("A altura deve ser maior que zero.", "INVALID_HEIGHT")
    if not MIN_HEIGHT_M <= value <= MAX_HEIGHT_M:
        raise unprocessable("A altura deve estar entre 0,5 m e 2,8 m.", "INVALID_HEIGHT")
    return value


def require_idempotency_key(raw: str) -> str:
    key = raw.strip()
    if not key:
        raise unprocessable("O campo idempotency_key é obrigatório.", "MISSING_IDEMPOTENCY_KEY")
    if len(key) > 128:
        raise unprocessable("idempotency_key é longo demais (máx. 128).", "INVALID_IDEMPOTENCY_KEY")
    return key


def _probe_duration_s(path: Path, ffprobe: str) -> float | None:
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(  # noqa: S603 — operator-configured ffprobe binary
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        LOGGER.info("ffprobe unavailable or failed: %s", exc)
        return None
    if completed.returncode != 0:
        LOGGER.info("ffprobe exited %s: %s", completed.returncode, completed.stderr[-200:])
        return None
    try:
        payload = json.loads(completed.stdout)
        duration = float(payload["format"]["duration"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
    return duration if duration > 0 else None


async def _write_upload(upload: UploadFile, dest: Path, remaining_budget: int) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with dest.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > remaining_budget:
                dest.unlink(missing_ok=True)
                raise unprocessable(
                    "O arquivo excede o tamanho máximo permitido.",
                    "UPLOAD_TOO_LARGE",
                )
            handle.write(chunk)
    await upload.close()
    return written


async def save_uploads(
    *,
    settings: Settings,
    user_id: str,
    job_id: str,
    video: UploadFile | None,
    images: list[UploadFile],
) -> SavedUpload:
    if video is not None and images:
        raise unprocessable("Envie um vídeo ou um conjunto de imagens, não ambos.", "AMBIGUOUS_SOURCE")
    if video is None and not images:
        raise unprocessable("Envie um vídeo (campo file) ou imagens (campo files[]).", "MISSING_SOURCE")

    root = settings.resolved_data_root()
    upload_dir = root / user_id / job_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    budget = settings.max_upload_bytes()

    if video is not None:
        filename = safe_filename(video.filename, "video.mp4")
        ext = suffix_of(filename)
        if ext not in VIDEO_EXTENSIONS:
            raise unprocessable(
                f"Extensão de vídeo não suportada ({ext or 'sem extensão'}). Use mp4, mov, mkv, webm ou avi.",
                "INVALID_VIDEO_EXTENSION",
            )
        dest = upload_dir / filename
        await _write_upload(video, dest, budget)
        duration = _probe_duration_s(dest, settings.tool_ffprobe)
        if duration is not None and duration > settings.max_video_duration_s:
            dest.unlink(missing_ok=True)
            minutes = int(settings.max_video_duration_s // 60)
            raise unprocessable(
                f"O vídeo é longo demais (máximo {minutes} minutos).",
                "VIDEO_TOO_LONG",
            )
        return SavedUpload(source_kind="video", paths=(dest,), original_names=(filename,))

    if len(images) < settings.min_images:
        raise unprocessable(
            f"Envie pelo menos {settings.min_images} imagens.",
            "TOO_FEW_IMAGES",
        )
    saved: list[Path] = []
    names: list[str] = []
    remaining = budget
    for index, image in enumerate(images):
        filename = safe_filename(image.filename, f"image_{index:04d}.jpg")
        ext = suffix_of(filename)
        if ext not in IMAGE_EXTENSIONS:
            raise unprocessable(
                f"Extensão de imagem não suportada ({ext or 'sem extensão'}). Use jpg, png ou heic.",
                "INVALID_IMAGE_EXTENSION",
            )
        dest = upload_dir / filename
        if dest.exists():
            dest = upload_dir / f"{index:04d}_{filename}"
        written = await _write_upload(image, dest, remaining)
        remaining -= written
        saved.append(dest)
        names.append(filename)
    return SavedUpload(source_kind="images", paths=tuple(saved), original_names=tuple(names))
