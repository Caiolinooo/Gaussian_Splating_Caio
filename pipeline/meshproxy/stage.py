"""Optional post-training job stage: Gaussian PLY → ``proxy.glb``.

This module is the **only** contract ``pipeline/jobs`` should import when
the consolidator plugs mesh-proxy as an optional stage. Do **not** import
``jobs``, ``train`` or ``export`` from here — the layout below is copied
as documentation, not as a dependency.

Job integration (for the consolidator)
======================================

When
----
After ``exporting`` (master ``.ply`` exists), before or after ``autocal``::

    … → training → exporting → [meshproxy] → autocal → done

The stage is optional: skip it when Open3D is missing or the product flag
is off. Failures use ``MeshProxyError.code`` / ``.user_message`` the same
way ingest/SfM/train do.

Signature
---------
``meshproxy_stage(context) -> dict``

``context`` is a :class:`MeshProxyContext` **or** a mapping with at least
``work_dir``. Additional keys override defaults (``ply_path``, ``out_glb``,
``depth``, ``simplify_target``, ``density_percentile``, ``min_points``,
``knn_k``, ``std_ratio``, ``opacity_threshold``).

Return value (``MeshProxyStageResult``)::

    {
        "artifacts": {"proxy_glb": "<abs path>", "proxy_obj": "<abs>"?},
        "metrics": {
            "points_in": int,         # vertices read from the PLY
            "points_filtered": int,   # centres kept after cleanup
            "faces": int,             # triangles in the written mesh
            "duration_s": float,
        },
        "message": str,               # pt-BR, UI-safe
    }

On-disk layout (mirrors ``jobs.paths.JobPaths``, not imported)
--------------------------------------------------------------
Preferred input:  ``{work_dir}/export/master.ply``
Fallback input:   ``{work_dir}/train/ply/point_cloud_*.ply`` (latest)
Output:           ``{work_dir}/export/proxy.glb``
                  ``{work_dir}/export/proxy.obj`` if GLB write fails
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, TypedDict

from ._deps import AVAILABLE
from .errors import BackendUnavailableError, meshproxy_too_large, missing_ply
from .filtering import (
    DEFAULT_DENSITY_PERCENTILE,
    DEFAULT_KNN_K,
    DEFAULT_OPACITY_THRESHOLD,
    DEFAULT_STD_RATIO,
)
from .io_ply import ply_vertex_count
from .reconstruct import (
    DEFAULT_MIN_POINTS,
    DEFAULT_POISSON_DEPTH,
    DEFAULT_SIMPLIFY_TARGET,
    ProxyBuildResult,
    build_proxy,
)

LOGGER = logging.getLogger("pipeline.meshproxy")

MASTER_PLY_REL = Path("export") / "master.ply"
OUTPUT_GLB_REL = Path("export") / "proxy.glb"
TRAIN_PLY_GLOB = "train/ply/point_cloud_*.ply"
# Stdlib KNN on a full 3DGS cloud hangs the job worker for hours.
MAX_MESHPROXY_VERTICES = 40_000

ProgressFn = Callable[[float, str], None]


class MeshProxyMetrics(TypedDict):
    points_in: int
    points_filtered: int
    faces: int
    duration_s: float


class MeshProxyStageResult(TypedDict):
    artifacts: dict[str, str]
    metrics: MeshProxyMetrics
    message: str


@dataclass(frozen=True, slots=True)
class MeshProxyContext:
    """Snapshot the job worker passes in. No handle to the job machine."""

    work_dir: Path
    ply_path: Path | None = None
    out_glb: Path | None = None
    depth: int = DEFAULT_POISSON_DEPTH
    simplify_target: int = DEFAULT_SIMPLIFY_TARGET
    density_percentile: float = DEFAULT_DENSITY_PERCENTILE
    min_points: int = DEFAULT_MIN_POINTS
    knn_k: int = DEFAULT_KNN_K
    std_ratio: float = DEFAULT_STD_RATIO
    opacity_threshold: float = DEFAULT_OPACITY_THRESHOLD
    progress: ProgressFn | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> MeshProxyContext:
        if "work_dir" not in payload:
            raise ValueError("meshproxy_stage context requires work_dir")
        allowed = {item.name for item in fields(cls)}
        kwargs: dict[str, Any] = {
            key: value for key, value in payload.items() if key in allowed
        }
        kwargs["work_dir"] = Path(kwargs["work_dir"])
        for name in ("ply_path", "out_glb"):
            if kwargs.get(name) is not None:
                kwargs[name] = Path(kwargs[name])
        return cls(**kwargs)


def resolve_master_ply(context: MeshProxyContext) -> Path:
    """Pick the 3DGS master PLY from an explicit path or the job layout."""
    if context.ply_path is not None:
        path = Path(context.ply_path)
        if path.is_file():
            return path
        raise missing_ply(str(path))

    master = Path(context.work_dir) / MASTER_PLY_REL
    if master.is_file():
        return master

    train_hits = sorted(
        Path(context.work_dir).glob(TRAIN_PLY_GLOB),
        key=step_sort_key,
    )
    if train_hits:
        return train_hits[-1]
    raise missing_ply(str(master))


def step_sort_key(path: Path) -> tuple[int, str]:
    """
    Ordena `point_cloud_<step>.ply` pelo número do step, não por texto.

    Ordem lexicográfica erra feio: "point_cloud_6999.ply" vem DEPOIS de
    "point_cloud_29999.ply" porque "6" > "2". Como o último item da lista é o
    escolhido como mestre, isso fazia o meshproxy usar um checkpoint antigo.
    """
    match = re.search(r"(\d+)", path.stem)
    if match is None:
        return (-1, path.name)
    return (int(match.group(1)), path.name)


def resolve_out_glb(context: MeshProxyContext) -> Path:
    if context.out_glb is not None:
        return Path(context.out_glb)
    return Path(context.work_dir) / OUTPUT_GLB_REL


def make_stage_result(
    built: ProxyBuildResult,
    *,
    message: str | None = None,
) -> MeshProxyStageResult:
    """Pure metrics/artifact dict — testable without Open3D."""
    artifacts: dict[str, str] = {}
    if built.glb_path is not None:
        artifacts["proxy_glb"] = str(built.glb_path)
    if built.obj_path is not None:
        artifacts["proxy_obj"] = str(built.obj_path)
    faces = built.faces
    return {
        "artifacts": artifacts,
        "metrics": {
            "points_in": built.points_in,
            "points_filtered": built.points_filtered,
            "faces": faces,
            "duration_s": built.duration_s,
        },
        "message": message
        or (
            f"Malha proxy gerada ({faces} faces, "
            f"{built.points_filtered} pontos após a limpeza)."
        ),
    }


def meshproxy_stage(
    context: MeshProxyContext | Mapping[str, Any],
) -> MeshProxyStageResult:
    """Run the optional proxy stage. See the module docstring for the contract."""
    ctx = (
        context
        if isinstance(context, MeshProxyContext)
        else MeshProxyContext.from_mapping(context)
    )
    _report(ctx, 0.05, "Localizando o .ply mestre…")
    ply_path = resolve_master_ply(ctx)
    vertex_count = ply_vertex_count(ply_path)
    if vertex_count > MAX_MESHPROXY_VERTICES:
        raise meshproxy_too_large(vertex_count, MAX_MESHPROXY_VERTICES)
    if not AVAILABLE:
        raise BackendUnavailableError()
    out_glb = resolve_out_glb(ctx)
    _report(ctx, 0.15, "Limpando a nuvem de gaussianas…")
    LOGGER.info("event=meshproxy_start ply=%s out=%s", ply_path, out_glb)
    built = build_proxy(
        ply_path,
        out_glb,
        depth=ctx.depth,
        simplify_target=ctx.simplify_target,
        density_percentile=ctx.density_percentile,
        min_points=ctx.min_points,
        knn_k=ctx.knn_k,
        std_ratio=ctx.std_ratio,
        opacity_threshold=ctx.opacity_threshold,
    )
    result = make_stage_result(built)
    _report(ctx, 1.0, result["message"])
    return result


def _report(context: MeshProxyContext, fraction: float, message: str) -> None:
    if context.progress is not None:
        context.progress(fraction, message)
