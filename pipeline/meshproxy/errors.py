"""Proxy-mesh errors. Identifiers in English; ``user_message`` in pt-BR."""

from __future__ import annotations

from typing import Never

SPARSE_CLOUD_USER = (
    "A nuvem de gaussianas ficou esparsa demais para gerar a malha proxy "
    "({n} pontos após a limpeza; mínimo {minimum}). "
    "Filme de novo com mais cobertura e textura, ou reduza o corte de densidade."
)

MISSING_PLY_USER = (
    "O arquivo .ply mestre não foi encontrado. "
    "Conclua o treino e o export antes de gerar a malha proxy."
)

INVALID_PLY_USER = (
    "O arquivo .ply não é um splat 3DGS válido "
    "(cabeçalho ilegível ou sem coordenadas x, y, z)."
)

UNSUPPORTED_PLY_USER = (
    "Este .ply usa um formato binário que a malha proxy não lê "
    "(apenas little-endian ou ASCII). Reexporte o splat mestre."
)

EMPTY_MESH_USER = (
    "A reconstrução Poisson não gerou faces. "
    "A nuvem pode ser plana ou esparsa demais — "
    "filme com mais cobertura ou tente de novo após o treino."
)

EXPORT_FAILED_USER = (
    "Não foi possível gravar a malha proxy (GLB/OBJ). "
    "Verifique o espaço em disco e as permissões da pasta do job."
)

OPEN3D_UNAVAILABLE_USER = (
    "A malha proxy precisa do Open3D, que não está instalado neste ambiente. "
    "Instale as dependências de "
    "pipeline/meshproxy/requirements-meshproxy.txt "
    "(Open3D é opcional e pesado)."
)

NO_FACES_AFTER_CROP_USER = (
    "O corte por densidade removeu a malha inteira. "
    "Reduza o percentil de densidade e tente de novo."
)

MESHPROXY_TOO_LARGE_USER = (
    "A malha proxy foi pulada: o splat tem {n} gaussianas "
    "(limite {limit} para o KNN em Python). "
    "Overlays usam o fallback sem proxy.glb."
)


class MeshProxyError(Exception):
    """Recoverable proxy-mesh failure with an actionable pt-BR message."""

    def __init__(self, message: str, *, user_message: str, code: str) -> None:
        super().__init__(message)
        self.user_message = user_message
        self.code = code


class BackendUnavailableError(MeshProxyError):
    """Raised only when reconstruction runs and Open3D/NumPy is missing."""

    def __init__(self) -> None:
        super().__init__(
            "Open3D is not installed",
            user_message=OPEN3D_UNAVAILABLE_USER,
            code="OPEN3D_UNAVAILABLE",
        )


class SparseCloudError(MeshProxyError):
    """Not enough Gaussian centres remain after filtering."""


def assert_never(value: Never) -> Never:
    raise AssertionError(f"unhandled value: {value!r}")


def missing_ply(path: str) -> MeshProxyError:
    return MeshProxyError(
        f"missing master ply: {path}",
        user_message=MISSING_PLY_USER,
        code="MISSING_PLY",
    )


def invalid_ply(detail: str) -> MeshProxyError:
    return MeshProxyError(
        f"invalid ply: {detail}",
        user_message=INVALID_PLY_USER,
        code="INVALID_PLY",
    )


def unsupported_ply(detail: str) -> MeshProxyError:
    return MeshProxyError(
        f"unsupported ply: {detail}",
        user_message=UNSUPPORTED_PLY_USER,
        code="UNSUPPORTED_PLY",
    )


def sparse_cloud(count: int, minimum: int) -> SparseCloudError:
    return SparseCloudError(
        f"sparse cloud: {count} < {minimum}",
        user_message=SPARSE_CLOUD_USER.format(n=count, minimum=minimum),
        code="SPARSE_CLOUD",
    )


def empty_mesh(detail: str) -> MeshProxyError:
    return MeshProxyError(
        f"empty poisson mesh: {detail}",
        user_message=EMPTY_MESH_USER,
        code="EMPTY_MESH",
    )


def export_failed(detail: str) -> MeshProxyError:
    return MeshProxyError(
        f"proxy export failed: {detail}",
        user_message=EXPORT_FAILED_USER,
        code="EXPORT_FAILED",
    )


def no_faces_after_crop() -> MeshProxyError:
    return MeshProxyError(
        "density crop removed every vertex",
        user_message=NO_FACES_AFTER_CROP_USER,
        code="EMPTY_MESH",
    )


def meshproxy_too_large(count: int, limit: int) -> MeshProxyError:
    return MeshProxyError(
        f"meshproxy cloud too large: {count} > {limit}",
        user_message=MESHPROXY_TOO_LARGE_USER.format(n=count, limit=limit),
        code="MESHPROXY_TOO_LARGE",
    )
