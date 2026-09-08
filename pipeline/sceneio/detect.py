"""Classify upload paths into a single SourceKind. No parallel pipelines."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ingest.config import SUPPORTED_IMAGE_SUFFIXES, SUPPORTED_VIDEO_SUFFIXES
from ingest.errors import IngestError
from jobs.states import SourceKind

PLY_SUFFIXES: frozenset[str] = frozenset({".ply"})
GIF_SUFFIXES: frozenset[str] = frozenset({".gif"})
# Reserved: a folder of frame_*.ply or splat sequence is future 4D, still one kind.
SEQUENCE_HINT_SUFFIXES: frozenset[str] = frozenset({".plyseq", ".4dgs"})


def _suffix(path: Path) -> str:
    return path.suffix.lower()


def skips_reconstruction(kind: SourceKind) -> bool:
    """PLY (and future imported 4D sequences) already are splats — no SfM/train."""
    return kind is SourceKind.PLY


def detect_source_kind(paths: Sequence[Path | str]) -> SourceKind:
    """Infer kind from filenames. Mixed media is rejected."""
    resolved = [Path(item) for item in paths]
    if not resolved:
        raise IngestError(
            "empty source list",
            user_message="Envie um vídeo, um GIF, um PLY ou um conjunto de imagens.",
            code="MISSING_SOURCE",
        )

    kinds: list[SourceKind] = []
    for path in resolved:
        suffix = _suffix(path)
        if suffix in PLY_SUFFIXES:
            kinds.append(SourceKind.PLY)
        elif suffix in GIF_SUFFIXES:
            kinds.append(SourceKind.GIF)
        elif suffix in SUPPORTED_VIDEO_SUFFIXES:
            kinds.append(SourceKind.VIDEO)
        elif suffix in SUPPORTED_IMAGE_SUFFIXES:
            kinds.append(SourceKind.IMAGES)
        else:
            raise IngestError(
                f"unsupported suffix: {suffix}",
                user_message=(
                    f"Formato não suportado ({suffix or 'sem extensão'}). "
                    "Use MP4/MOV/WEBM, GIF, PLY ou imagens JPG/PNG/HEIC."
                ),
                code="INVALID_FORMAT",
            )

    unique = set(kinds)
    if len(unique) > 1:
        raise IngestError(
            f"mixed kinds: {sorted(k.value for k in unique)}",
            user_message="Envie só um tipo de origem por job (vídeo, GIF, PLY ou imagens).",
            code="AMBIGUOUS_SOURCE",
        )

    kind = kinds[0]
    if kind is SourceKind.PLY and len(resolved) != 1:
        raise IngestError(
            "multiple ply files",
            user_message="Envie um único arquivo .ply por job. Sequências 4D ainda não são treinadas.",
            code="AMBIGUOUS_SOURCE",
        )
    if kind is SourceKind.GIF and len(resolved) != 1:
        raise IngestError(
            "multiple gifs",
            user_message="Envie um único GIF por job.",
            code="AMBIGUOUS_SOURCE",
        )
    if kind is SourceKind.VIDEO and len(resolved) != 1:
        raise IngestError(
            "multiple videos",
            user_message="Envie um único vídeo por job.",
            code="AMBIGUOUS_SOURCE",
        )
    return kind
