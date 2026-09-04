"""Supabase JWT verification (HS256 primary; JWKS/ES256 best-effort).

HS256 is implemented with the standard library (``hmac`` + ``hashlib``).
ES256/RS256 via JWKS requires the optional ``cryptography`` package.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from typing import Any

try:
    from jwt import PyJWKClient
    from jwt import decode as jwt_decode

    _HAS_PYJWT = True
except ImportError:
    PyJWKClient = None  # type: ignore[misc, assignment]
    jwt_decode = None  # type: ignore[misc, assignment]
    _HAS_PYJWT = False

from app.core.config import Settings
from app.core.errors import unauthorized

_JWKS_CACHE: dict[str, Any] | None = None
_JWKS_CACHED_AT = 0.0
_JWKS_TTL_S = 3600.0
_CLOCK_SKEW_S = 30


class TokenError(ValueError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def encode_hs256(payload: dict[str, Any], secret: str, *, headers: dict[str, Any] | None = None) -> str:
    """Create a compact HS256 JWT (used by tests and the local bypass helpers)."""
    header = {"alg": "HS256", "typ": "JWT"}
    if headers:
        header.update(headers)
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def _split_token(token: str) -> tuple[str, str, str]:
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise TokenError("Token inválido.", "TOKEN_INVALID")
    return parts[0], parts[1], parts[2]


def decode_unverified(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    header_b64, payload_b64, _sig = _split_token(token)
    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenError("Token inválido.", "TOKEN_INVALID") from exc
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise TokenError("Token inválido.", "TOKEN_INVALID")
    return header, payload


def _verify_hs256(token: str, secret: str) -> dict[str, Any]:
    header_b64, payload_b64, sig_b64 = _split_token(token)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        actual = _b64url_decode(sig_b64)
    except ValueError as exc:
        raise TokenError("Token inválido.", "TOKEN_INVALID") from exc
    if not hmac.compare_digest(expected, actual):
        raise TokenError("Token inválido ou assinatura não confere.", "TOKEN_INVALID")
    header, payload = decode_unverified(token)
    if header.get("alg") != "HS256":
        raise TokenError("Algoritmo de token não suportado.", "UNSUPPORTED_ALG")
    return payload


def _validate_claims(payload: dict[str, Any]) -> dict[str, Any]:
    now = int(time.time())
    exp = payload.get("exp")
    if exp is not None:
        try:
            expired = now > int(exp) + _CLOCK_SKEW_S
        except (TypeError, ValueError) as exc:
            raise TokenError("Token inválido.", "TOKEN_INVALID") from exc
        if expired:
            raise TokenError("Sessão expirada. Entre novamente.", "TOKEN_EXPIRED")
    nbf = payload.get("nbf")
    if nbf is not None:
        try:
            too_early = now + _CLOCK_SKEW_S < int(nbf)
        except (TypeError, ValueError) as exc:
            raise TokenError("Token inválido.", "TOKEN_INVALID") from exc
        if too_early:
            raise TokenError("Token ainda não é válido.", "TOKEN_INVALID")
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise TokenError("Token sem identificador de usuário.", "TOKEN_INVALID")
    role = payload.get("role")
    if role == "anon":
        raise TokenError("Token anônimo não é aceito.", "TOKEN_INVALID")
    return payload


def _jwks_url(settings: Settings) -> str:
    if settings.supabase_jwks_url:
        return settings.supabase_jwks_url
    base = settings.supabase_url.rstrip("/")
    if not base:
        raise TokenError(
            "Token ES256/JWKS exige SUPABASE_URL ou SUPABASE_JWKS_URL.",
            "JWKS_UNAVAILABLE",
        )
    return f"{base}/auth/v1/.well-known/jwks.json"


def _fetch_jwks(settings: Settings) -> dict[str, Any]:
    global _JWKS_CACHE, _JWKS_CACHED_AT
    now = time.time()
    if _JWKS_CACHE is not None and now - _JWKS_CACHED_AT < _JWKS_TTL_S:
        return _JWKS_CACHE
    url = _jwks_url(settings)
    try:
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 — operator-configured JWKS URL
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        raise TokenError("Não foi possível validar o token (JWKS indisponível).", "JWKS_UNAVAILABLE") from exc
    if not isinstance(payload, dict):
        raise TokenError("JWKS inválido.", "JWKS_UNAVAILABLE")
    _JWKS_CACHE = payload
    _JWKS_CACHED_AT = now
    return payload


def _verify_jwks(token: str, header: dict[str, Any], settings: Settings) -> dict[str, Any]:
    if not _HAS_PYJWT or PyJWKClient is None or jwt_decode is None:
        raise TokenError(
            "Token ES256/RS256 exige PyJWT + cryptography no deploy (HS256 é o caminho primário).",
            "UNSUPPORTED_ALG",
        )

    url = _jwks_url(settings)
    try:
        client = PyJWKClient(url)
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt_decode(
            token,
            signing_key.key,
            algorithms=[str(header.get("alg") or "ES256")],
            options={"verify_aud": False},
        )
    except Exception as exc:  # noqa: BLE001 — map any JWKS/crypto failure to 401
        raise TokenError("Token inválido ou JWKS recusou a assinatura.", "TOKEN_INVALID") from exc
    if not isinstance(payload, dict):
        raise TokenError("Token inválido.", "TOKEN_INVALID")
    return payload


def verify_supabase_jwt(token: str, settings: Settings) -> dict[str, Any]:
    header, _payload = decode_unverified(token)
    alg = str(header.get("alg") or "")
    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise TokenError("Servidor sem SUPABASE_JWT_SECRET configurado.", "AUTH_MISCONFIGURED")
        claims = _verify_hs256(token, settings.supabase_jwt_secret)
        return _validate_claims(claims)
    if alg in {"ES256", "RS256"}:
        _fetch_jwks(settings)  # fail fast if JWKS is unreachable
        claims = _verify_jwks(token, header, settings)
        return _validate_claims(claims)
    raise TokenError("Algoritmo de token não suportado.", "UNSUPPORTED_ALG")


def claims_or_http(token: str, settings: Settings) -> dict[str, Any]:
    try:
        return verify_supabase_jwt(token, settings)
    except TokenError as exc:
        raise unauthorized(exc.message, exc.code) from exc
