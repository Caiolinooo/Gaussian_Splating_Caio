"""Login local opcional: usuário único configurado por env, sem Supabase."""

from __future__ import annotations

import hmac
import time

from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.errors import unauthorized, unprocessable
from app.core.jwtutil import encode_hs256
from app.deps import get_settings
from app.schemas.auth import LocalAuthInfo, LocalLoginRequest, LocalLoginResponse, LocalLoginUser

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_TTL_S = 7 * 24 * 3600


def _configured(settings: Settings) -> bool:
    return bool(settings.local_auth_user.strip()) and bool(settings.local_auth_password)


@router.get("/local", response_model=LocalAuthInfo)
def local_auth_info(settings: Settings = Depends(get_settings)) -> LocalAuthInfo:
    """A tela de login usa para pré-preencher o usuário padrão."""
    if not _configured(settings):
        return LocalAuthInfo(enabled=False)
    return LocalAuthInfo(enabled=True, username=settings.local_auth_user.strip())


@router.post("/login", response_model=LocalLoginResponse)
def local_login(payload: LocalLoginRequest, settings: Settings = Depends(get_settings)) -> LocalLoginResponse:
    if not _configured(settings):
        raise unprocessable("Login local não está habilitado neste servidor.", "LOCAL_AUTH_DISABLED")
    if not settings.supabase_jwt_secret:
        raise unprocessable(
            "Servidor sem SUPABASE_JWT_SECRET para assinar a sessão local.",
            "AUTH_MISCONFIGURED",
        )

    expected_user = settings.local_auth_user.strip()
    user_ok = hmac.compare_digest(payload.username.strip(), expected_user)
    password_ok = hmac.compare_digest(payload.password, settings.local_auth_password)
    if not (user_ok and password_ok):
        raise unauthorized("Usuário ou senha incorretos.", "INVALID_CREDENTIALS")

    now = int(time.time())
    email = expected_user if "@" in expected_user else None
    claims: dict[str, object] = {
        "sub": expected_user,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + SESSION_TTL_S,
    }
    if email:
        claims["email"] = email
    token = encode_hs256(claims, settings.supabase_jwt_secret)
    return LocalLoginResponse(
        access_token=token,
        expires_in=SESSION_TTL_S,
        user=LocalLoginUser(id=expected_user, email=email),
    )
