"""Supabase Auth dependency and the local development bypass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, Request, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, settings
from app.core.errors import unauthorized
from app.core.jwtutil import claims_or_http

DEV_USER_ID = "dev-user"

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    email: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)
    via_bypass: bool = False


def settings_from_request(request: Request) -> Settings:
    return getattr(request.app.state, "settings", settings)


def _user_from_token(token: str, cfg: Settings) -> CurrentUser:
    claims = claims_or_http(token, cfg)
    email = claims.get("email")
    return CurrentUser(
        user_id=str(claims["sub"]),
        email=email if isinstance(email, str) else None,
        claims=claims,
    )


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, remainder = authorization.partition(" ")
    if scheme.lower() != "bearer" or not remainder.strip():
        return None
    return remainder.strip()


def authenticate_token(token: str | None, cfg: Settings) -> CurrentUser:
    if cfg.dev_auth_bypass:
        return CurrentUser(user_id=DEV_USER_ID, via_bypass=True)
    if not token:
        raise unauthorized()
    return _user_from_token(token, cfg)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    cfg = settings_from_request(request)
    token = credentials.credentials if credentials is not None else None
    return authenticate_token(token, cfg)


async def authenticate_websocket(websocket: WebSocket) -> CurrentUser:
    cfg: Settings = getattr(websocket.app.state, "settings", settings)
    header_token = _extract_bearer(websocket.headers.get("authorization"))
    query_token = websocket.query_params.get("token") or websocket.query_params.get("access_token")
    token = header_token or query_token
    return authenticate_token(token, cfg)
