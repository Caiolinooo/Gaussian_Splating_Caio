"""gsplat trainer errors (pt-BR for the user)."""

from __future__ import annotations


class TrainError(Exception):
    def __init__(self, message: str, *, user_message: str, code: str) -> None:
        super().__init__(message)
        self.user_message = user_message
        self.code = code


def trainer_failed(detail: str) -> TrainError:
    return TrainError(
        detail,
        user_message=(
            "O treino 3DGS falhou. "
            "Confira se o ambiente GPU está saudável e tente novamente."
        ),
        code="TRAINER_FAILED",
    )


def missing_dataset(path: str) -> TrainError:
    return TrainError(
        f"missing COLMAP dataset: {path}",
        user_message="O dataset COLMAP não foi encontrado. Refaça a etapa de SfM.",
        code="MISSING_DATASET",
    )


def no_metrics() -> TrainError:
    return TrainError(
        "trainer produced no metrics",
        user_message="O treino terminou sem métricas de qualidade. Veja o log da etapa.",
        code="NO_METRICS",
    )
