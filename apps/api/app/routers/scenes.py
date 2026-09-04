"""Versioned scene JSON stored per user."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.deps import get_scene_store
from app.schemas.scenes import SceneDocument
from app.services.scene_store import SceneStore

router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.get("/{scene_id}", response_model=SceneDocument)
def get_scene(
    scene_id: str,
    user: CurrentUser = Depends(get_current_user),
    store: SceneStore = Depends(get_scene_store),
) -> SceneDocument:
    return store.get(user.user_id, scene_id)


@router.put("/{scene_id}", response_model=SceneDocument)
def put_scene(
    scene_id: str,
    body: SceneDocument,
    user: CurrentUser = Depends(get_current_user),
    store: SceneStore = Depends(get_scene_store),
) -> SceneDocument:
    return store.put(user.user_id, scene_id, body)
