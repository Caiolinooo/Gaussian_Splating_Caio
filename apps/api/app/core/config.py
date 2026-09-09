"""Environment-backed API settings (pydantic-settings when available).

Recognised env vars: ``DATA_ROOT``, ``SUPABASE_JWT_SECRET``, ``SUPABASE_URL``,
``SUPABASE_JWKS_URL``, ``DEV_AUTH_BYPASS``, ``PIPELINE_PATH``, ``MAX_UPLOAD_MB``,
``MAX_VIDEO_DURATION_S``, ``MIN_IMAGES``, ``TOOL_FFMPEG``, ``TOOL_FFPROBE``,
``TOOL_COLMAP``, ``TOOL_PYTHON``, ``TOOL_SIMPLE_TRAINER``, ``TOOL_SPLAT_TRANSFORM``,
``TRAIN_MAX_STEPS``, ``TRAIN_DATA_FACTOR``, ``TRAIN_SH_DEGREE``,
``COLMAP_MIN_REGISTERED_COUNT``, ``COLMAP_MIN_REGISTERED_RATIO``,
``COLMAP_MAX_EXHAUSTIVE_IMAGES``, ``COLMAP_USE_GPU``, ``CORS_ORIGINS``,
``SERVE_WEB_DIR``, ``LOCAL_AUTH_USER``, ``LOCAL_AUTH_PASSWORD``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

from pydantic import BeforeValidator, Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    _HAS_PYDANTIC_SETTINGS = True
except ImportError:  # documented fallback — no extra package required for tests
    from pydantic import BaseModel as BaseSettings

    class SettingsConfigDict(dict):  # type: ignore[no-redef]
        """Stand-in when ``pydantic-settings`` is not installed."""

    _HAS_PYDANTIC_SETTINGS = False

_API_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:2222",
    "http://127.0.0.1:2222",
    "http://vm.groupabz.com:2222",
    "https://vm.groupabz.com:2222",
    "tauri://localhost",
    "http://tauri.localhost",
)


def _as_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _as_path(raw: str) -> Path:
    return Path(raw)


def parse_cors_origins(value: object) -> list[str]:
    """Accept a JSON list, comma-separated hosts, or ``*``."""
    if value is None:
        return list(DEFAULT_CORS_ORIGINS)
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return list(DEFAULT_CORS_ORIGINS)
    if text.startswith("["):
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        return list(DEFAULT_CORS_ORIGINS)
    return [part.strip() for part in text.split(",") if part.strip()]


CorsOrigins = Annotated[list[str], BeforeValidator(parse_cors_origins)]


def _optional_path(raw: str) -> Path | None:
    text = raw.strip()
    if not text:
        return None
    return Path(text)


def _read_env() -> dict[str, Any]:
    """Map uppercase env vars onto Settings field names."""
    mapping: dict[str, tuple[str, Any]] = {
        "APP_NAME": ("app_name", str),
        "DATA_ROOT": ("data_root", _as_path),
        "SUPABASE_JWT_SECRET": ("supabase_jwt_secret", str),
        "SUPABASE_URL": ("supabase_url", str),
        "SUPABASE_JWKS_URL": ("supabase_jwks_url", str),
        "DEV_AUTH_BYPASS": ("dev_auth_bypass", _as_bool),
        "PIPELINE_PATH": ("pipeline_path", _as_path),
        "MAX_UPLOAD_MB": ("max_upload_mb", int),
        "MAX_VIDEO_DURATION_S": ("max_video_duration_s", float),
        "MIN_IMAGES": ("min_images", int),
        "TOOL_FFMPEG": ("tool_ffmpeg", str),
        "TOOL_FFPROBE": ("tool_ffprobe", str),
        "TOOL_COLMAP": ("tool_colmap", str),
        "TOOL_PYTHON": ("tool_python", str),
        "TOOL_SIMPLE_TRAINER": ("tool_simple_trainer", str),
        "TOOL_SPLAT_TRANSFORM": ("tool_splat_transform", str),
        "TRAIN_MAX_STEPS": ("train_max_steps", int),
        "TRAIN_DATA_FACTOR": ("train_data_factor", int),
        "TRAIN_SH_DEGREE": ("train_sh_degree", int),
        "COLMAP_MIN_REGISTERED_COUNT": ("colmap_min_registered_count", int),
        "COLMAP_MIN_REGISTERED_RATIO": ("colmap_min_registered_ratio", float),
        "COLMAP_MAX_EXHAUSTIVE_IMAGES": ("colmap_max_exhaustive_images", int),
        "COLMAP_USE_GPU": ("colmap_use_gpu", _as_bool),
        "CORS_ORIGINS": ("cors_origins", parse_cors_origins),
        "SERVE_WEB_DIR": ("serve_web_dir", _optional_path),
        "LOCAL_AUTH_USER": ("local_auth_user", str),
        "LOCAL_AUTH_PASSWORD": ("local_auth_password", str),
    }
    values: dict[str, Any] = {}
    for env_name, (field_name, conv) in mapping.items():
        raw = os.environ.get(env_name)
        if raw is None or raw == "":
            continue
        values[field_name] = conv(raw)
    return values


class Settings(BaseSettings):
    """Immutable-enough configuration loaded from the process environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Gaussian Splatting — API local"
    version: str = "0.2.0"
    cors_origins: CorsOrigins = Field(default_factory=lambda: list(DEFAULT_CORS_ORIGINS))
    serve_web_dir: Path | None = None
    data_root: Path = Path("data")
    supabase_jwt_secret: str = ""
    supabase_url: str = ""
    supabase_jwks_url: str = ""
    dev_auth_bypass: bool = False
    # Login local sem Supabase: quando ambos definidos, POST /auth/login emite
    # JWT HS256 (assinado com supabase_jwt_secret) para este usuário.
    local_auth_user: str = ""
    local_auth_password: str = ""
    pipeline_path: Path = Path("../../pipeline")
    max_upload_mb: int = 2048
    max_video_duration_s: float = 1200.0
    min_images: int = 20
    tool_ffmpeg: str = "ffmpeg"
    tool_ffprobe: str = "ffprobe"
    tool_colmap: str = "colmap"
    tool_python: str = "python"
    tool_simple_trainer: str = "simple_trainer.py"
    tool_splat_transform: str = "splat-transform"
    train_max_steps: int = 30_000
    train_data_factor: int = 2
    train_sh_degree: int = 3
    colmap_min_registered_count: int = 20
    colmap_min_registered_ratio: float = 0.70
    colmap_max_exhaustive_images: int = 220
    # Quando True, o SfM tenta GPU primeiro e cai para CPU automaticamente se
    # feature_extractor/matcher falharem (servidor headless sem contexto GL).
    colmap_use_gpu: bool = True

    def resolved_data_root(self) -> Path:
        path = self.data_root if self.data_root.is_absolute() else Path.cwd() / self.data_root
        return path.resolve()

    def resolved_pipeline_path(self) -> Path:
        raw = self.pipeline_path
        if raw.is_absolute():
            return raw.resolve()
        return (_API_ROOT / raw).resolve()

    def resolved_serve_web_dir(self) -> Path | None:
        raw = self.serve_web_dir
        if raw is None:
            return None
        path = raw if raw.is_absolute() else Path.cwd() / raw
        resolved = path.resolve()
        return resolved if resolved.is_dir() else None

    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb) * 1024 * 1024


def load_settings() -> Settings:
    if _HAS_PYDANTIC_SETTINGS:
        return Settings()
    return Settings(**_read_env())


settings = load_settings()
