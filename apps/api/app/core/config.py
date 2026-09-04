"""Configurações da API local (Fase 0: valores fixos; env vars chegam com a Fase 1)."""

from pydantic import BaseModel


class Settings(BaseModel):
    """Configuração imutável da aplicação."""

    app_name: str = "Gaussian Splatting — API local"
    version: str = "0.1.0"
    cors_origins: list[str] = [
        "http://localhost:5173",  # dev server do apps/web (Vite)
        "http://127.0.0.1:5173",
        "tauri://localhost",  # webview do Tauri (Linux/macOS)
        "http://tauri.localhost",  # webview do Tauri (Windows)
    ]


settings = Settings()
