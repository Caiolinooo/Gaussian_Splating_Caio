"""Export-stage errors (pt-BR)."""

from __future__ import annotations


class ExportError(Exception):
    def __init__(self, message: str, *, user_message: str, code: str) -> None:
        super().__init__(message)
        self.user_message = user_message
        self.code = code


def missing_ply(path: str) -> ExportError:
    return ExportError(
        f"missing master ply: {path}",
        user_message="O arquivo .ply mestre não foi gerado. Refaça o treino.",
        code="MISSING_PLY",
    )


def transform_failed(detail: str) -> ExportError:
    return ExportError(
        detail,
        user_message=(
            "A conversão para .ksplat falhou. "
            "Verifique se o splat-transform está instalado no ambiente."
        ),
        code="TRANSFORM_FAILED",
    )


def thumbnail_failed(detail: str) -> ExportError:
    return ExportError(
        detail,
        user_message="Não foi possível gerar a miniatura da cena.",
        code="THUMBNAIL_FAILED",
    )
