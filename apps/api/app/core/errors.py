"""HTTP errors with a stable pt-BR payload ``{message, code}``."""

from fastapi import HTTPException, status


def api_error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"message": message, "code": code})


def unauthorized(
    message: str = "Não autenticado. Envie um token Bearer válido.",
    code: str = "UNAUTHENTICATED",
) -> HTTPException:
    return api_error(status.HTTP_401_UNAUTHORIZED, message, code)


def forbidden(message: str = "Você não tem permissão para acessar este recurso.") -> HTTPException:
    return api_error(status.HTTP_403_FORBIDDEN, message, "FORBIDDEN")


def not_found(message: str, code: str = "NOT_FOUND") -> HTTPException:
    return api_error(status.HTTP_404_NOT_FOUND, message, code)


def conflict(message: str, code: str = "CONFLICT", extra: dict[str, object] | None = None) -> HTTPException:
    detail: dict[str, object] = {"message": message, "code": code}
    if extra:
        detail.update(extra)
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def unprocessable(message: str, code: str = "VALIDATION_ERROR") -> HTTPException:
    return api_error(422, message, code)


def unavailable(message: str = "O orquestrador de jobs não está disponível no momento.") -> HTTPException:
    return api_error(status.HTTP_503_SERVICE_UNAVAILABLE, message, "PIPELINE_UNAVAILABLE")
