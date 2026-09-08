"""User-facing ingest errors (messages in pt-BR)."""

from __future__ import annotations


class IngestError(Exception):
    """Raised when video or image intake cannot proceed."""

    def __init__(self, message: str, *, user_message: str, code: str) -> None:
        super().__init__(message)
        self.user_message = user_message
        self.code = code


def invalid_format(path: str, suffix: str) -> IngestError:
    return IngestError(
        f"unsupported image format: {path}",
        user_message=(
            f"Formato não suportado ({suffix or 'desconhecido'}). "
            "Envie JPG, PNG, WebP, TIFF ou HEIC."
        ),
        code="INVALID_FORMAT",
    )


def too_small(path: str, width: int, height: int, min_width: int, min_height: int) -> IngestError:
    return IngestError(
        f"image too small: {path} {width}x{height}",
        user_message=(
            f"A imagem é muito pequena ({width}×{height} px). "
            f"Use no mínimo {min_width}×{min_height} px."
        ),
        code="TOO_SMALL",
    )


def video_unreadable(path: str, detail: str) -> IngestError:
    return IngestError(
        f"unreadable video: {path}: {detail}",
        user_message=(
            "Não foi possível ler o vídeo ou GIF. "
            "Verifique se o arquivo não está corrompido e tente outro formato (MP4/MOV/GIF)."
        ),
        code="VIDEO_UNREADABLE",
    )


def too_few_frames(count: int, minimum: int) -> IngestError:
    return IngestError(
        f"too few usable frames: {count} < {minimum}",
        user_message=(
            f"Só restaram {count} frames nítidos (mínimo {minimum}). "
            "Grave com mais tempo, menos movimento brusco e melhor iluminação."
        ),
        code="TOO_FEW_FRAMES",
    )


def empty_image_set() -> IngestError:
    return IngestError(
        "empty image set",
        user_message="Nenhuma imagem válida foi enviada. Envie pelo menos algumas fotos do ambiente.",
        code="EMPTY_SET",
    )


def heic_unsupported(path: str) -> IngestError:
    return IngestError(
        f"HEIC probe failed: {path}",
        user_message=(
            "Não foi possível abrir o arquivo HEIC. "
            "Converta para JPG/PNG ou instale o suporte HEIC no ambiente."
        ),
        code="HEIC_UNSUPPORTED",
    )
