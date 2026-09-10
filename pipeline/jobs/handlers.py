"""Default stage handlers (real binaries). Tests inject fakes instead."""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from export.config import ExportConfig
from geom.planes import densify_points3d_txt
from ingest.config import ToolBins
from jobs.autocal import AutocalContext, AutocalHook, AutocalResult
from jobs.autocal_adapter import PipelineAutocal
from jobs.models import JobRecord
from jobs.paths import JobPaths, job_paths
from jobs.runner import CommandRunner, SubprocessRunner
from jobs.states import SourceKind
from provisioner.bins import resolve_python_bin
from relight.sh_env import build_relight_env, write_relight_document
from sceneio.detect import skips_reconstruction
from sceneio.export import export_scene, refresh_scene_calibration
from sceneio.ingest import ingest_scene
from sfm.commands import build_model_converter_bin_command
from sfm.config import ColmapConfig, ColmapPaths
from temporal.clusters import build_temporal_scene, write_temporal_document
from temporal.normalize import trainer_normalizes_world
from temporal.flow_rigs import write_4dgs_npz

try:
    from meshproxy.errors import BackendUnavailableError, MeshProxyError
    from meshproxy.stage import meshproxy_stage
except ImportError:  # optional stage — package or Open3D extras may be absent
    BackendUnavailableError = None  # type: ignore[misc, assignment]
    MeshProxyError = None  # type: ignore[misc, assignment]
    meshproxy_stage = None
from sfm.runner import run_sfm
from train.commands import latest_ply
from train.config import TrainConfig, resolve_eval_train_steps
from train.runner import run_training

LOGGER = logging.getLogger("pipeline.jobs.handlers")


@dataclass(frozen=True)
class StageOutcome:
    artifacts: dict[str, str]
    metrics: dict[str, Any]
    message: str = ""
    skipped: bool = False


StageFn = Callable[[JobRecord, Callable[[float, str], None]], StageOutcome]


@dataclass
class StageHandlers:
    extract: StageFn
    sfm: StageFn
    training: StageFn
    exporting: StageFn
    meshproxy: StageFn
    autocal: StageFn

    def get(self, stage: str) -> StageFn:
        mapping = {
            "extracting": self.extract,
            "sfm": self.sfm,
            "training": self.training,
            "exporting": self.exporting,
            "meshproxy": self.meshproxy,
            "autocal": self.autocal,
        }
        try:
            return mapping[stage]
        except KeyError as exc:
            raise AssertionError(f"unhandled stage: {stage}") from exc


def _relink(link: Path, target: Path) -> None:
    target = target.resolve()
    if link.exists() or link.is_symlink():
        if link.is_symlink() or link.is_file():
            link.unlink()
        else:
            shutil.rmtree(link)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        shutil.copytree(target, link)


def _colmap_source_kind(kind: SourceKind) -> str:
    if kind is SourceKind.VIDEO or kind is SourceKind.GIF:
        return "video"
    return "images"


def handle_extract(record: JobRecord, progress: Callable[[float, str], None], runner: CommandRunner) -> StageOutcome:
    paths = job_paths(record.work_path)
    paths.ensure()
    result = ingest_scene(
        [Path(item) for item in record.source.paths],
        paths,
        video_ingest=record.video_ingest,
        image_ingest=record.image_ingest,
        tools=ToolBins(ffmpeg=record.tools.ffmpeg, ffprobe=record.tools.ffprobe),
        runner=runner,
        progress=progress,
        kind=record.source.kind,
    )
    if result.frames_dir is not None:
        _relink(paths.dataset_dir / "images", result.frames_dir)
    record.extra["temporal"] = dict(result.temporal)
    record.extra["skip_reconstruction"] = result.skip_reconstruction
    return StageOutcome(
        artifacts=dict(result.artifacts),
        metrics=dict(result.metrics),
        message=result.message,
    )


def handle_sfm(record: JobRecord, progress: Callable[[float, str], None], runner: CommandRunner) -> StageOutcome:
    if skips_reconstruction(record.source.kind):
        progress(1.0, "PLY já é splat — SfM não é necessário.")
        return StageOutcome(
            artifacts={},
            metrics={"skipped": True, "reason": "ply_import"},
            message="PLY já é splat — SfM não é necessário.",
            skipped=True,
        )
    paths = job_paths(record.work_path)
    image_dir = paths.dataset_dir / "images"
    if not image_dir.exists():
        image_dir = paths.kept_frames_dir
    colmap_cfg = ColmapConfig(
        colmap_bin=record.tools.colmap,
        matcher=record.colmap.matcher,
        camera_model=record.colmap.camera_model,
        single_camera=record.colmap.single_camera,
        use_gpu=record.colmap.use_gpu,
        sequential_overlap=record.colmap.sequential_overlap,
        sequential_quadratic_overlap=record.colmap.sequential_quadratic_overlap,
        min_registered_ratio=record.colmap.min_registered_ratio,
        min_registered_count=record.colmap.min_registered_count,
        max_exhaustive_images=record.colmap.max_exhaustive_images,
        timeout_s=record.colmap.timeout_s,
        mapper_multiple_models=record.colmap.mapper_multiple_models,
        mapper_max_num_models=record.colmap.mapper_max_num_models,
        mapper_init_num_trials=record.colmap.mapper_init_num_trials,
        mapper_ba_global_max_num_iterations=record.colmap.mapper_ba_global_max_num_iterations,
        sift_peak_threshold=record.colmap.sift_peak_threshold,
        sift_edge_threshold=record.colmap.sift_edge_threshold,
        sift_max_num_features=record.colmap.sift_max_num_features,
    )
    result = run_sfm(
        colmap_cfg,
        ColmapPaths(image_dir=image_dir, work_dir=paths.colmap_dir),
        runner,
        source_kind=_colmap_source_kind(record.source.kind),
        progress=progress,
    )
    _relink(paths.dataset_dir / "sparse", paths.colmap_sparse)
    prior = {"input_points": 0, "planes": 0, "added": 0}
    points_txt = Path(result.model_dir) / "points3D.txt"
    if points_txt.is_file():
        prior = densify_points3d_txt(points_txt)
        if prior.get("added", 0) > 0:
            try:
                runner.run(build_model_converter_bin_command(colmap_cfg, Path(result.model_dir)))
            except Exception:
                LOGGER.warning("event=points3d_bin_convert_failed model=%s", result.model_dir)
    return StageOutcome(
        artifacts={
            "model_dir": str(result.model_dir),
            "database": str(paths.colmap_db),
            "dataset_dir": str(paths.dataset_dir),
            "log": str(result.log_path),
        },
        metrics={
            "registered": result.summary.registered_count,
            "input_images": result.summary.input_image_count,
            "ratio": result.summary.ratio,
            "matcher": result.matcher,
            "used_gpu": result.used_gpu,
            "selected_sparse": result.selected_sparse,
            "warning": result.summary.warning,
            "wall_planes": prior.get("planes", 0),
            "wall_points_added": prior.get("added", 0),
        },
        message=result.summary.warning or f"{result.summary.registered_count} imagens registradas.",
    )


def handle_training(record: JobRecord, progress: Callable[[float, str], None], runner: CommandRunner) -> StageOutcome:
    if skips_reconstruction(record.source.kind):
        progress(1.0, "PLY já é splat — treino 3DGS não é necessário.")
        return StageOutcome(
            artifacts={},
            metrics={"skipped": True, "reason": "ply_import"},
            message="PLY já é splat — treino 3DGS não é necessário.",
            skipped=True,
        )
    paths = job_paths(record.work_path)
    extract = record.stages.get("extracting")
    kept_frames = 0
    if extract is not None and extract.metrics.get("kept_frames") is not None:
        kept_frames = int(extract.metrics["kept_frames"])
    configured_steps = record.train.max_steps
    steps = resolve_eval_train_steps(kept_frames, configured_steps)
    save_steps = (steps,) if steps != configured_steps else record.train.save_steps
    eval_steps = (steps,) if steps != configured_steps else record.train.eval_steps
    ply_steps = (steps,) if steps != configured_steps else record.train.ply_steps
    python_bin = resolve_python_bin(record.tools.python)
    record.tools.python = python_bin
    train_cfg = TrainConfig(
        python_bin=python_bin,
        trainer_script=Path(record.tools.simple_trainer),
        subcommand=record.train.subcommand,
        data_factor=record.train.data_factor,
        max_steps=steps,
        save_steps=save_steps,
        eval_steps=eval_steps,
        ply_steps=ply_steps,
        save_ply=record.train.save_ply,
        disable_viewer=record.train.disable_viewer,
        disable_video=record.train.disable_video,
        extra_args=record.train.extra_args,
        timeout_s=record.train.timeout_s,
    )
    result = run_training(
        train_cfg,
        data_dir=paths.dataset_dir,
        result_dir=paths.train_dir,
        runner=runner,
        progress=progress,
        extra_log_dir=paths.logs_dir,
    )
    artifacts = {"result_dir": str(result.result_dir)}
    if result.ply_path is not None:
        artifacts["ply"] = str(result.ply_path)
    if result.ckpt_path is not None:
        artifacts["ckpt"] = str(result.ckpt_path)
    log_path = paths.train_dir / "train.log"
    if log_path.is_file():
        artifacts["train_log"] = str(log_path)
    sfm_model = Path(record.stages.get("sfm").artifacts.get("model_dir") or "") if record.stages.get("sfm") else Path()
    prior_temporal = record.extra.get("temporal") if isinstance(record.extra.get("temporal"), dict) else {}
    temporal_scene = build_temporal_scene(
        points3d_txt=sfm_model / "points3D.txt" if (sfm_model / "points3D.txt").is_file() else None,
        images_txt=sfm_model / "images.txt" if (sfm_model / "images.txt").is_file() else None,
        frame_count=kept_frames,
        duration_s=(
            prior_temporal.get("durationS")
            if isinstance(prior_temporal.get("durationS"), (int, float))
            else None
        ),
        fps=prior_temporal.get("fps") if isinstance(prior_temporal.get("fps"), (int, float)) else None,
        source_kind=str(prior_temporal.get("sourceKind") or record.source.kind.value),
        frames_dir=paths.kept_frames_dir if paths.kept_frames_dir.is_dir() else paths.frames_dir,
        normalize_world_space=trainer_normalizes_world(record.train.extra_args),
    )
    record.extra["temporal"] = temporal_scene.to_document()
    relight_env = build_relight_env(sh_degree=3)
    record.extra["relight"] = relight_env.to_document()
    write_temporal_document(paths.export_dir / "temporal.json", temporal_scene)
    write_relight_document(paths.export_dir / "relight.json", relight_env)
    trajectories = [
        [list(key.get("t") or [0.0, 0.0, 0.0]) for key in cluster.get("keys", [])]
        for cluster in temporal_scene.clusters
    ]
    write_4dgs_npz(paths.export_dir / "4dgs.npz", list(temporal_scene.times), trajectories)
    artifacts["temporal"] = str(paths.export_dir / "temporal.json")
    artifacts["relight"] = str(paths.export_dir / "relight.json")
    artifacts["4dgs"] = str(paths.export_dir / "4dgs.npz")
    return StageOutcome(
        artifacts=artifacts,
        metrics={
            "psnr_val": result.metrics.psnr_val,
            "num_gaussians": result.metrics.num_gaussians,
            "duration_s": result.metrics.duration_s,
            "ssim_val": result.metrics.ssim_val,
            "python_bin": python_bin,
            "temporal_cameras": len(temporal_scene.cameras),
            "temporal_clusters": len(temporal_scene.clusters),
            "relight": True,
        },
        message="Treino 3DGS + 4D/relight concluído.",
    )


def handle_export(record: JobRecord, progress: Callable[[float, str], None], runner: CommandRunner) -> StageOutcome:
    paths = job_paths(record.work_path)
    ply = Path(record.stages["training"].artifacts.get("ply") or "")
    if not ply.is_file():
        extracted = Path(record.stages["extracting"].artifacts.get("ply") or "")
        if extracted.is_file():
            ply = extracted
        else:
            found = latest_ply(paths.train_dir)
            ply = found if found is not None else paths.master_ply
    export_cfg = ExportConfig(
        splat_transform_bin=record.tools.splat_transform,
        ffmpeg_bin=record.tools.ffmpeg,
        filter_nan=record.export.filter_nan,
        filter_floaters=record.export.filter_floaters,
        floater_voxel=record.export.floater_voxel,
        floater_opacity=record.export.floater_opacity,
        floater_min_contribution=record.export.floater_min_contribution,
        web_sh_degree=record.export.web_sh_degree,
        thumbnail_max_edge=record.export.thumbnail_max_edge,
        thumbnail_name=record.export.thumbnail_name,
        timeout_s=record.export.timeout_s,
    )
    temporal = record.extra.get("temporal") if isinstance(record.extra.get("temporal"), dict) else None
    relight = record.extra.get("relight") if isinstance(record.extra.get("relight"), dict) else None
    result = export_scene(
        export_cfg,
        source_ply=ply,
        export_dir=paths.export_dir,
        runner=runner,
        scene_id=record.job_id,
        scene_name=f"Job {record.job_id[:8]}",
        render_dir=paths.train_dir / "renders",
        frames_dir=paths.kept_frames_dir if paths.kept_frames_dir.is_dir() else None,
        calibration_path=paths.calibration_json if paths.calibration_json.is_file() else None,
        temporal=temporal,  # type: ignore[arg-type]
        relight=relight,  # type: ignore[arg-type]
        progress=progress,
    )
    artifacts = {
        "master_ply": str(result.master_ply),
        "scene_json": str(result.scene_json),
        "scene_package": str(result.scene_package),
    }
    if result.ksplat_written:
        artifacts["web_ksplat"] = str(result.web_ksplat)
    if result.thumbnail is not None:
        artifacts["thumbnail"] = str(result.thumbnail)
    message = (
        "Export .ply + .ksplat + cena (JSON/zip) concluído."
        if result.ksplat_written
        else "Export .ply + cena (JSON/zip) concluído; .ksplat omitido (splat-transform ausente)."
    )
    return StageOutcome(
        artifacts=artifacts,
        metrics={"ksplat": result.ksplat_written, "package": True},
        message=message,
    )


def handle_meshproxy(record: JobRecord, progress: Callable[[float, str], None]) -> StageOutcome:
    if skips_reconstruction(record.source.kind):
        progress(1.0, "PLY importado — malha proxy não se aplica.")
        return StageOutcome(
            artifacts={},
            metrics={"skipped": True, "reason": "ply_import"},
            message="PLY importado — malha proxy não se aplica.",
            skipped=True,
        )
    progress(0.05, "Gerando malha proxy…")
    if meshproxy_stage is None or BackendUnavailableError is None or MeshProxyError is None:
        return StageOutcome(
            artifacts={},
            metrics={"skipped": True, "code": "OPEN3D_UNAVAILABLE"},
            message="Malha proxy indisponível neste ambiente; overlays usarão fallback.",
            skipped=True,
        )
    try:
        result = meshproxy_stage({"work_dir": record.work_dir, "progress": progress})
    except BackendUnavailableError as exc:
        return StageOutcome(
            artifacts={},
            metrics={"skipped": True, "code": exc.code},
            message=exc.user_message,
            skipped=True,
        )
    except MeshProxyError as exc:
        if exc.code in {"OPEN3D_UNAVAILABLE", "MESHPROXY_TOO_LARGE"}:
            return StageOutcome(
                artifacts={},
                metrics={"skipped": True, "code": exc.code},
                message=exc.user_message,
                skipped=True,
            )
        raise
    return StageOutcome(
        artifacts=dict(result["artifacts"]),
        metrics=dict(result["metrics"]),
        message=result["message"],
    )


def handle_autocal(record: JobRecord, progress: Callable[[float, str], None], hook: AutocalHook) -> StageOutcome:
    if skips_reconstruction(record.source.kind):
        progress(1.0, "PLY importado — auto-calibração por frames não se aplica.")
        return StageOutcome(
            artifacts={},
            metrics={"skipped": True, "reason": "ply_import"},
            message="PLY importado — auto-calibração por frames não se aplica.",
            skipped=True,
        )
    paths = job_paths(record.work_path)
    progress(0.1, "Estimando escala pela altura informada…")
    frames = record.stages["extracting"].artifacts.get("frames_dir") or str(paths.kept_frames_dir)
    sfm_model = ""
    sfm_stage = record.stages.get("sfm")
    if sfm_stage is not None:
        sfm_model = str(sfm_stage.artifacts.get("model_dir") or "")
    result: AutocalResult = hook.run(
        AutocalContext(
            job_id=record.job_id,
            frames_dir=frames,
            user_height_m=record.user_height_m,
            registered_names=(),
            colmap_model_dir=sfm_model,
        )
    )
    payload = result.scene_calibration or {
        "scaleFactor": result.scale_factor,
        "source": result.source,
        "confidence": result.confidence,
        "framesUsed": result.frames_used,
        "estimatedPersonHeightSceneUnits": None,
        "errorEstimate": None,
        "warnings": [],
    }
    paths.export_dir.mkdir(parents=True, exist_ok=True)
    calib_path = paths.calibration_json
    calib_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    refresh_scene_calibration(paths.export_dir, payload)
    progress(1.0, result.message)
    return StageOutcome(
        artifacts={"calibration": str(calib_path)},
        metrics={
            "scale_factor": result.scale_factor,
            "source": result.source,
            "confidence": result.confidence,
            "frames_used": result.frames_used,
        },
        message=result.message,
    )


def default_handlers(
    runner: CommandRunner | None = None,
    autocal: AutocalHook | None = None,
) -> StageHandlers:
    execute = runner or SubprocessRunner()
    hook = autocal or PipelineAutocal()
    return StageHandlers(
        extract=lambda record, progress: handle_extract(record, progress, execute),
        sfm=lambda record, progress: handle_sfm(record, progress, execute),
        training=lambda record, progress: handle_training(record, progress, execute),
        exporting=lambda record, progress: handle_export(record, progress, execute),
        meshproxy=handle_meshproxy,
        autocal=lambda record, progress: handle_autocal(record, progress, hook),
    )


def job_layout(record: JobRecord) -> JobPaths:
    return job_paths(record.work_path)
