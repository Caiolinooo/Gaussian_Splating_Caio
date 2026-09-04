"""Per-user versioned scene documents on disk."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.core.errors import conflict, forbidden, not_found, unprocessable
from app.schemas.scenes import SCENE_SCHEMA_VERSION, SceneDocument

_SCENE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def validate_scene_id(scene_id: str) -> str:
    if not _SCENE_ID_RE.match(scene_id):
        raise unprocessable("Identificador de cena inválido.", "INVALID_SCENE_ID")
    return scene_id


class SceneStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _path(self, user_id: str, scene_id: str) -> Path:
        validate_scene_id(scene_id)
        root = self._settings.resolved_data_root()
        path = (root / user_id / "scenes" / f"{scene_id}.json").resolve()
        user_root = (root / user_id).resolve()
        try:
            path.relative_to(user_root)
        except ValueError as exc:
            raise forbidden("Caminho de cena inválido.") from exc
        return path

    def get(self, user_id: str, scene_id: str) -> SceneDocument:
        path = self._path(user_id, scene_id)
        if not path.is_file():
            raise not_found("Cena não encontrada.", "SCENE_NOT_FOUND")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return SceneDocument.model_validate(payload)

    def put(self, user_id: str, scene_id: str, incoming: SceneDocument) -> SceneDocument:
        if incoming.schema_version != SCENE_SCHEMA_VERSION:
            raise unprocessable(
                f"schema_version não suportado (esperado {SCENE_SCHEMA_VERSION}).",
                "UNSUPPORTED_SCHEMA",
            )
        path = self._path(user_id, scene_id)
        document = incoming.model_copy(update={"id": scene_id})
        if path.is_file():
            current = SceneDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))
            if document.version != current.version:
                raise conflict(
                    "A cena foi alterada por outra sessão. Recarregue e tente novamente.",
                    "VERSION_CONFLICT",
                    extra={"current_version": current.version},
                )
            document = document.model_copy(update={"version": current.version + 1, "updated_at": utc_now()})
        else:
            document = document.model_copy(update={"version": 1, "updated_at": utc_now()})
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(document.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(path)
        return document
