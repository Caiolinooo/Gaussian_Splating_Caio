"""Resolve job artifacts without path traversal."""

from __future__ import annotations

from pathlib import Path

from app.core.assert_never import assert_never
from app.core.config import Settings
from app.core.errors import forbidden, not_found
from app.schemas.jobs import ArtifactKind

_THUMBNAIL_GLOBS: tuple[str, ...] = ("preview.jpg", "preview.png", "*.jpg", "*.jpeg", "*.png")


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def artifact_relpath(kind: ArtifactKind) -> tuple[str, ...]:
    match kind:
        case ArtifactKind.PLY:
            return ("export", "master.ply")
        case ArtifactKind.KSPLAT:
            return ("export", "scene.ksplat")
        case ArtifactKind.THUMBNAIL:
            return ("export", "thumbnails", "preview.jpg")
        case ArtifactKind.LOG:
            return ("colmap", "colmap.log")
        case ArtifactKind.SCENE:
            return ("export", "scene.json")
        case ArtifactKind.PACKAGE:
            return ("export", "scene.zip")
        case _:
            assert_never(kind)


def media_type_for(kind: ArtifactKind) -> str:
    match kind:
        case ArtifactKind.PLY:
            return "application/octet-stream"
        case ArtifactKind.KSPLAT:
            return "application/octet-stream"
        case ArtifactKind.THUMBNAIL:
            return "image/jpeg"
        case ArtifactKind.LOG:
            return "text/plain; charset=utf-8"
        case ArtifactKind.SCENE:
            return "application/json"
        case ArtifactKind.PACKAGE:
            return "application/zip"
        case _:
            assert_never(kind)


def _first_thumbnail(thumbs_dir: Path) -> Path | None:
    if not thumbs_dir.is_dir():
        return None
    for pattern in _THUMBNAIL_GLOBS:
        matches = sorted(thumbs_dir.glob(pattern))
        for candidate in matches:
            if candidate.is_file():
                return candidate
    return None


def resolve_artifact(*, work_dir: Path, kind: ArtifactKind, settings: Settings, user_id: str) -> Path:
    data_root = settings.resolved_data_root()
    work = work_dir.resolve()
    if not _is_under(work, data_root):
        raise forbidden("Caminho de artefato inválido.")
    user_root = (data_root / user_id).resolve()
    if not _is_under(work, user_root):
        raise forbidden("Caminho de artefato inválido.")

    relative = artifact_relpath(kind)
    candidate = (work.joinpath(*relative)).resolve()
    if not _is_under(candidate, work):
        raise forbidden("Caminho de artefato inválido.")

    if candidate.is_file():
        return candidate

    if kind is ArtifactKind.THUMBNAIL:
        fallback = _first_thumbnail(work / "export" / "thumbnails")
        if fallback is not None and _is_under(fallback.resolve(), work):
            return fallback.resolve()

    raise not_found("Artefato ainda não disponível.", "ARTIFACT_NOT_READY")
