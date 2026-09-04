"""Environment-backed API settings (pydantic-settings when available).

Recognised env vars: ``DATA_ROOT``, ``SUPABASE_JWT_SECRET``, ``SUPABASE_URL``,
``SUPABASE_JWKS_URL``, ``DEV_AUTH_BYPASS``, ``PIPELINE_PATH``, ``MAX_UPLOAD_MB``,
``MAX_VIDEO_DURATION_S``, ``MIN_IMAGES``, ``TOOL_FFMPEG``, ``TOOL_FFPROBE``,
``TOOL_COLMAP``, ``TOOL_PYTHON``, ``TOOL_SIMPLE_TRAINER``, ``TOOL_SPLAT_TRANSFORM``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    _HAS_PYDANTIC_SETTINGS = True
except ImportError:  # documented fallback — no extra package required for tests
    from pydantic import BaseModel as BaseSettings

    class SettingsConfigDict(dict):  # type: ignore[no-redef]
        """Stand-in when ``pydantic-settings`` is not installed."""

    _HAS_PYDANTIC_SETTINGS = False

_API_ROOT = Path(__file__).resolve().parents[2]


def _as_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _as_path(raw: str) -> Path:
    return Path(raw)


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
    version: str = "0.1.0"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "tauri://localhost",
            "http://tauri.localhost",
        ]
    )
    data_root: Path = Path("data")
    supabase_jwt_secret: str = ""
    supabase_url: str = ""
    supabase_jwks_url: str = ""
    dev_auth_bypass: bool = False
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

    def resolved_data_root(self) -> Path:
        path = self.data_root if self.data_root.is_absolute() else Path.cwd() / self.data_root
        return path.resolve()

    def resolved_pipeline_path(self) -> Path:
        raw = self.pipeline_path
        if raw.is_absolute():
            return raw.resolve()
        return (_API_ROOT / raw).resolve()

    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb) * 1024 * 1024


def load_settings() -> Settings:
    if _HAS_PYDANTIC_SETTINGS:
        return Settings()
    return Settings(**_read_env())


settings = load_settings()
