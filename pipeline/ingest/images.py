"""Still-image intake: validate format/size and copy into a versioned folder."""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ingest.config import SUPPORTED_IMAGE_SUFFIXES, ImageInfo, ImageIngestConfig
from ingest.errors import (
    empty_image_set,
    heic_unsupported,
    invalid_format,
    too_small,
)
from ingest.quality import compute_normalized_size

try:
    from PIL import Image
except ImportError:
    Image = None

LOGGER = logging.getLogger("pipeline.ingest.images")

ProgressFn = Callable[[float, str], None]
ImageProber = Callable[[Path], ImageInfo]


def next_version_dir(base: Path) -> Path:
    """Return ``base/v00N`` with N = max(existing)+1 (starts at 1)."""
    base.mkdir(parents=True, exist_ok=True)
    highest = 0
    for child in base.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if len(name) >= 2 and name[0] == "v" and name[1:].isdigit():
            highest = max(highest, int(name[1:]))
    return base / f"v{highest + 1:03d}"


def collect_image_paths(sources: Sequence[Path]) -> list[Path]:
    files: list[Path] = []
    for source in sources:
        if source.is_dir():
            for child in sorted(source.iterdir()):
                if child.is_file():
                    files.append(child)
            continue
        if source.is_file():
            files.append(source)
    return files


def probe_image(path: Path) -> ImageInfo:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        raise invalid_format(str(path), suffix)
    if Image is None:
        return ImageInfo(path=path, width=0, height=0, format=suffix.lstrip("."), suffix=suffix)
    try:
        with Image.open(path) as handle:
            handle.load()
            width, height = handle.size
            fmt = (handle.format or suffix.lstrip(".")).lower()
    except Exception as exc:
        if suffix in {".heic", ".heif"}:
            raise heic_unsupported(str(path)) from exc
        raise invalid_format(str(path), suffix) from exc
    return ImageInfo(path=path, width=width, height=height, format=fmt, suffix=suffix)


def validate_image_info(info: ImageInfo, config: ImageIngestConfig) -> ImageInfo:
    suffix = info.suffix.lower() or f".{info.format}"
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    allowed = {item.lower() for item in config.allowed_suffixes}
    if suffix not in allowed and info.format.lower() not in {item.lstrip(".") for item in allowed}:
        raise invalid_format(str(info.path), suffix)
    if info.width and info.height:
        if info.width < config.min_width or info.height < config.min_height:
            raise too_small(
                str(info.path),
                info.width,
                info.height,
                config.min_width,
                config.min_height,
            )
    return info


@dataclass(frozen=True)
class ImageIngestResult:
    version_dir: Path
    version: int
    copied: tuple[Path, ...]
    rejected: tuple[str, ...]
    infos: tuple[ImageInfo, ...]
    normalize_hint: tuple[int, int] | None


def ingest_images(
    sources: Sequence[Path],
    versions_root: Path,
    config: ImageIngestConfig,
    *,
    progress: ProgressFn | None = None,
    prober: ImageProber | None = None,
) -> ImageIngestResult:
    """Copy a validated still-image set into the next ``v00N`` folder (no ffmpeg)."""
    paths = collect_image_paths(tuple(Path(item) for item in sources))
    if not paths:
        raise empty_image_set()

    probe = prober or probe_image
    accepted: list[ImageInfo] = []
    rejected: list[str] = []
    total = len(paths)
    for index, path in enumerate(paths):
        if progress is not None:
            progress((index / max(total, 1)) * 0.6, f"Validando {path.name}…")
        try:
            info = validate_image_info(probe(path), config)
        except Exception as exc:
            user_message = getattr(exc, "user_message", None)
            rejected.append(f"{path.name}: {user_message or exc}")
            LOGGER.info("event=image_rejected path=%s reason=%s", path, exc)
            continue
        accepted.append(info)

    if not accepted:
        raise empty_image_set()

    version_dir = next_version_dir(versions_root)
    version_dir.mkdir(parents=True, exist_ok=False)
    copied: list[Path] = []
    for order, info in enumerate(accepted, start=1):
        dest = version_dir / f"image_{order:06d}{info.suffix.lower() or '.jpg'}"
        shutil.copy2(info.path, dest)
        copied.append(dest)

    widths = [info.width for info in accepted if info.width]
    heights = [info.height for info in accepted if info.height]
    hint: tuple[int, int] | None = None
    if widths and heights:
        hint = compute_normalized_size(
            max(widths),
            max(heights),
            max_edge=config.max_edge_px,
        )

    current = versions_root / "current.json"
    payload = {
        "version": int(version_dir.name[1:]),
        "directory": str(version_dir),
        "count": len(copied),
        "created_at": datetime.now(UTC).isoformat(),
        "rejected": rejected,
        "normalize_hint": list(hint) if hint else None,
    }
    current.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if progress is not None:
        progress(1.0, f"{len(copied)} imagens copiadas ({version_dir.name}).")
    LOGGER.info(
        "event=ingest_images_done version=%s kept=%s rejected=%s",
        version_dir.name,
        len(copied),
        len(rejected),
    )
    return ImageIngestResult(
        version_dir=version_dir,
        version=int(version_dir.name[1:]),
        copied=tuple(copied),
        rejected=tuple(rejected),
        infos=tuple(accepted),
        normalize_hint=hint,
    )


def iter_version_dirs(versions_root: Path) -> Iterable[Path]:
    if not versions_root.is_dir():
        return []
    dirs = [
        child
        for child in versions_root.iterdir()
        if child.is_dir() and child.name.startswith("v") and child.name[1:].isdigit()
    ]
    return sorted(dirs, key=lambda item: int(item.name[1:]))
