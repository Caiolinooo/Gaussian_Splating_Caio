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
        raise few_registered(registered, total, min_registered_ratio)
    if total and ratio < min_registered_ratio:
        raise few_registered(registered, total, min_registered_ratio)

    return ReconstructionSummary(
        registered_images=mapped,
        registered_count=registered,
        input_image_count=total,
        ratio=ratio,
        log_registered_ids=log_ids,
        raw_log=log_text,
    )


def explain_sfm_error(error: SfmError) -> str:
    """Return the user-facing pt-BR message (stable for the API)."""
    if error.code == "FEW_MATCHES":
        return FEW_MATCHES_USER
    return error.user_message
