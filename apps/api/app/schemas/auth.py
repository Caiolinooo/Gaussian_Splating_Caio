"""Contratos do login local (sem Supabase)."""

from __future__ import annotations

from pydantic import BaseModel


class LocalLoginRequest(BaseModel):
    username: str
    password: str


class LocalLoginUser(BaseModel):
    id: str
    email: str | None = None


class LocalLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: LocalLoginUser


class LocalAuthInfo(BaseModel):
    """Expõe apenas o necessário para a tela de login — nunca a senha."""

    enabled: bool
    username: str | None = None
