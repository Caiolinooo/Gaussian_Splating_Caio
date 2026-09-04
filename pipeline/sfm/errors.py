"""COLMAP / SfM errors with actionable pt-BR messages."""

from __future__ import annotations


class SfmError(Exception):
    def __init__(self, message: str, *, user_message: str, code: str) -> None:
        super().__init__(message)
        self.user_message = user_message
        self.code = code


FEW_MATCHES_USER = (
    "Poucas correspondências — grave com mais textura/luz. "
    "Evite paredes lisas, trechos escuros e movimentos muito rápidos."
)

FEW_REGISTERED_USER = (
    "Poucas imagens foram registradas no SfM. "
    "Filme com mais sobreposição entre os trechos, textura visível e luz uniforme."
)

NO_RECONSTRUCTION_USER = (
    "O COLMAP não conseguiu montar a cena 3D. "
    "Grave de novo com mais textura, sobreposição e iluminação estável."
)


def few_matches(detail: str) -> SfmError:
    return SfmError(detail, user_message=FEW_MATCHES_USER, code="FEW_MATCHES")


def few_registered(registered: int, total: int, minimum_ratio: float) -> SfmError:
    percent = int(round(minimum_ratio * 100))
    return SfmError(
        f"registered {registered}/{total} below {minimum_ratio:.2f}",
        user_message=(
            f"{FEW_REGISTERED_USER} "
            f"Registradas: {registered} de {total} (mínimo {percent}%)."
        ),
        code="FEW_REGISTERED",
    )


def no_reconstruction(detail: str) -> SfmError:
    return SfmError(detail, user_message=NO_RECONSTRUCTION_USER, code="NO_RECONSTRUCTION")


def colmap_failed(step: str, stderr: str) -> SfmError:
    return SfmError(
        f"colmap {step} failed: {stderr}",
        user_message=(
            f"A etapa COLMAP ({step}) falhou. "
            "Confira o log técnico ou tente gravar novamente com mais textura/luz."
        ),
        code="COLMAP_FAILED",
    )
