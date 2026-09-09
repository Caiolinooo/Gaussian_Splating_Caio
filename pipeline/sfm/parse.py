"""Parse COLMAP logs and ``images.txt`` reconstructions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sfm.errors import (
    FEW_MATCHES_USER,
    SfmError,
    few_matches,
    few_registered,
    no_reconstruction,
    subset_warning,
)

_IMAGE_LINE = re.compile(
    r"^\s*(\d+)\s+"
    r"(?:[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s+){7}"
    r"(\d+)\s+(\S+)\s*$"
)
_REGISTERED_LOG = re.compile(
    r"Registering image\s+#?(?P<id>\d+)",
    re.IGNORECASE,
)
_REGISTERED_COUNT = re.compile(
    r"Registered images:\s*(?P<n>\d+)",
    re.IGNORECASE,
)
_NO_PAIR = re.compile(
    r"no good initial image pair|could not find good initial image pair",
    re.IGNORECASE,
)
_FEW_MATCH = re.compile(
    r"not enough matches|insufficient matches|too few matches|0 matches",
    re.IGNORECASE,
)
_NO_MORE = re.compile(
    r"could not register any more images|failed to register",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RegisteredImage:
    image_id: int
    camera_id: int
    name: str


@dataclass(frozen=True)
class ReconstructionSummary:
    registered_images: tuple[RegisteredImage, ...]
    registered_count: int
    input_image_count: int
    ratio: float
    log_registered_ids: tuple[int, ...]
    raw_log: str
    warning: str | None = None

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.registered_images)


def parse_images_txt(text: str) -> tuple[RegisteredImage, ...]:
    """COLMAP text model: two lines per image (pose, then POINTS2D)."""
    images: list[RegisteredImage] = []
    expect_points = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if expect_points:
            expect_points = False
            continue
        match = _IMAGE_LINE.match(line)
        if match is None:
            continue
        images.append(
            RegisteredImage(
                image_id=int(match.group(1)),
                camera_id=int(match.group(2)),
                name=match.group(3),
            )
        )
        expect_points = True
    return tuple(images)


def parse_images_txt_file(path: Path) -> tuple[RegisteredImage, ...]:
    return parse_images_txt(path.read_text(encoding="utf-8", errors="replace"))


def parse_colmap_log(log_text: str) -> tuple[int, ...]:
    ids = [int(match.group("id")) for match in _REGISTERED_LOG.finditer(log_text)]
    count_match = list(_REGISTERED_COUNT.finditer(log_text))
    if count_match and not ids:
        # Some builds only print the aggregate line.
        return tuple(range(1, int(count_match[-1].group("n")) + 1))
    return tuple(ids)


def detect_sfm_failure(log_text: str) -> SfmError | None:
    if _NO_PAIR.search(log_text) or _FEW_MATCH.search(log_text):
        return few_matches(log_text[-500:] if log_text else "few matches")
    if _NO_MORE.search(log_text) and "Registering image" not in log_text:
        return no_reconstruction(log_text[-500:] if log_text else "no reconstruction")
    return None


def count_input_images(image_dir: Path) -> int:
    if not image_dir.is_dir():
        return 0
    return sum(1 for child in image_dir.iterdir() if child.is_file())


def count_points3d_txt(text: str) -> int:
    return sum(1 for raw in text.splitlines() if raw.strip() and not raw.lstrip().startswith("#"))


def list_sparse_models(sparse_dir: Path) -> tuple[Path, ...]:
    """Numeric COLMAP reconstructions (`sparse/0`, `sparse/3`, …) that have a model."""
    if not sparse_dir.is_dir():
        return ()
    found: list[Path] = []
    for child in sparse_dir.iterdir():
        if not child.is_dir() or not child.name.isdigit():
            continue
        if (child / "images.bin").is_file() or (child / "images.txt").is_file():
            found.append(child)
    return tuple(sorted(found, key=lambda item: int(item.name)))


def score_reconstruction(model_dir: Path) -> tuple[int, int]:
    """`(registered_images, points3D)`."""
    images_txt = model_dir / "images.txt"
    registered = len(parse_images_txt_file(images_txt)) if images_txt.is_file() else 0
    points_txt = model_dir / "points3D.txt"
    if points_txt.is_file():
        points = count_points3d_txt(points_txt.read_text(encoding="utf-8", errors="replace"))
    else:
        points = 0
    return (registered, points)


def rank_reconstruction(cameras: int, points: int) -> tuple[int, int, int]:
    """Structure first: 54 cams / 37 pts lose to 52 cams / 4066 pts."""
    structured = 1 if points >= max(200, cameras * 8) else 0
    return (structured, cameras, points)


def pick_largest_model(sparse_dir: Path) -> Path | None:
    """Prefer a triangulated model. Degenerate (few points) loses even with more cameras."""
    scored: list[tuple[tuple[int, int, int], Path]] = []
    for model in list_sparse_models(sparse_dir):
        cameras, points = score_reconstruction(model)
        if cameras > 0:
            scored.append((rank_reconstruction(cameras, points), model))
    if scored:
        return max(scored, key=lambda item: item[0])[1]
    models = list_sparse_models(sparse_dir)
    return models[0] if models else None


def summarize_reconstruction(
    *,
    images_txt: str | None,
    log_text: str,
    input_image_count: int,
    min_registered_ratio: float,
    min_registered_count: int,
) -> ReconstructionSummary:
    """Build a summary and raise ``SfmError`` when quality gates fail."""
    mapped = parse_images_txt(images_txt) if images_txt else ()
    log_ids = parse_colmap_log(log_text)
    registered = len(mapped) if mapped else len(log_ids)
    total = max(input_image_count, registered)
    ratio = (registered / total) if total else 0.0

    hard_fail = detect_sfm_failure(log_text)
    if hard_fail is not None and registered == 0:
        raise hard_fail
    if registered == 0:
        raise no_reconstruction("zero registered images")
    if registered < min_registered_count:
        raise few_registered(
            registered,
            total,
            min_registered_ratio,
            min_registered_count=min_registered_count,
        )
    warning = None
    if total and ratio < min_registered_ratio:
        warning = subset_warning(registered, total, min_registered_ratio)

    return ReconstructionSummary(
        registered_images=mapped,
        registered_count=registered,
        input_image_count=total,
        ratio=ratio,
        log_registered_ids=log_ids,
        raw_log=log_text,
        warning=warning,
    )


def explain_sfm_error(error: SfmError) -> str:
    """Return the user-facing pt-BR message (stable for the API)."""
    if error.code == "FEW_MATCHES":
        return FEW_MATCHES_USER
    return error.user_message
