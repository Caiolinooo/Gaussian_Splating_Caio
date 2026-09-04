"""Default stage handlers (real binaries). Tests inject fakes instead."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from export.config import ExportConfig
from export.runner import run_export
from ingest.config import ToolBins
from ingest.images import ingest_images
from ingest.video import ingest_video
from jobs.autocal import AutocalContext, AutocalHook, AutocalResult
from jobs.autocal_adapter import PipelineAutocal
from jobs.models import JobRecord
from jobs.paths import JobPaths, job_paths
from jobs.runner import CommandRunner, SubprocessRunner
from jobs.states import SourceKind, assert_never
from sfm.config import ColmapConfig, ColmapPaths

try:
    from meshproxy.errors import BackendUnavailableError, MeshProxyError
    from meshproxy.stage import meshproxy_stage
except ImportError:  # optional stage — package or Open3D extras may be absent
    BackendUnavailableError = None  # type: ignore[misc, assignment]
    MeshProxyError = None  # type: ignore[misc, assignment]
    meshproxy_stage = None
from sfm.runner import run_sfm
from train.commands import latest_ply
from train.config import TrainConfig
from train.runner import run_training


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


def handle_extract(record: JobRecord, progress: Callable[[float, str], None], runner: CommandRunner) -> StageOutcome:
    paths = job_paths(record.work_path)
    paths.ensure()
    kind = record.source.kind
    if kind is SourceKind.VIDEO:
        result = ingest_video(
            Path(record.source.paths[0]),
            paths.frames_dir,
            record.video_ingest,
            ToolBins(ffmpeg=record.tools.ffmpeg, ffprobe=record.tools.ffprobe),
            runner,
            progress=progress,
        )
        _relink(paths.dataset_dir / "images", result.frames_dir)
        return StageOutcome(
            artifacts={"frames_dir": str(result.frames_dir), "manifest": str(paths.frames_dir / "manifest.json")},
            metrics={
                "kept_frames": len(result.kept_paths),
                "strategy": result.rate.strategy,
                "extract_fps": result.rate.extract_fps,
                "dropped_blur": len(result.selection.dropped_blur),
                "dropped_dup": len(result.selection.dropped_dup),
            },
            message=f"{len(result.kept_paths)} frames extraídos.",
        )
    if kind is SourceKind.IMAGES:
        result = ingest_images(
            [Path(item) for item in record.source.paths],
            paths.images_versions_dir,
            record.image_ingest,
            progress=progress,
        )
        _relink(paths.dataset_dir / "images", result.version_dir)
        return StageOutcome(
            artifacts={"frames_dir": str(result.version_dir), "version": str(result.version)},
            metrics={"kept_frames": len(result.copied), "rejected": len(result.rejected)},
            message=f"{len(result.copied)} imagens validadas ({result.version_dir.name}).",
        )
    assert_never(kind)


def handle_sfm(record: JobRecord, progress: Callable[[float, str], None], runner: CommandRunner) -> StageOutcome:
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
        timeout_s=record.colmap.timeout_s,
    )
    result = run_sfm(
        colmap_cfg,
        ColmapPaths(image_dir=image_dir, work_dir=paths.colmap_dir),
        runner,
        source_kind=record.source.kind.value,
        progress=progress,
    )
    _relink(paths.dataset_dir / "sparse", paths.colmap_sparse)
    return StageOutcome(
        artifacts={
            "model_dir": str(result.model_dir),
            "database": str(paths.colmap_db),
            "dataset_dir": str(paths.dataset_dir),
        },
        metrics={
            "registered": result.summary.registered_count,
            "input_images": result.summary.input_image_count,
            "ratio": result.summary.ratio,
            "matcher": result.matcher,
        },
        message=f"{result.summary.registered_count} imagens registradas.",
    )


def handle_training(record: JobRecord, progress: Callable[[float, str], None], runner: CommandRunner) -> StageOutcome:
    paths = job_paths(record.work_path)
    train_cfg = TrainConfig(
        python_bin=record.tools.python,
        trainer_script=Path(record.tools.simple_trainer),
        subcommand=record.train.subcommand,
        data_factor=record.train.data_factor,
        max_steps=record.train.max_steps,
        save_steps=record.train.save_steps,
        eval_steps=record.train.eval_steps,
        ply_steps=record.train.ply_steps,
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
    )
    artifacts = {"result_dir": str(result.result_dir)}
    if result.ply_path is not None:
        artifacts["ply"] = str(result.ply_path)
    if result.ckpt_path is not None:
        artifacts["ckpt"] = str(result.ckpt_path)
    return StageOutcome(
        artifacts=artifacts,
        metrics={
            "psnr_val": result.metrics.psnr_val,
            "num_gaussians": result.metrics.num_gaussians,
            "duration_s": result.metrics.duration_s,
            "ssim_val": result.metrics.ssim_val,
        },
        message="Treino 3DGS concluído.",
    )


def handle_export(record: JobRecord, progress: Callable[[float, str], None], runner: CommandRunner) -> StageOutcome:
    paths = job_paths(record.work_path)
    ply = Path(record.stages["training"].artifacts.get("ply") or "")
    if not ply.is_file():
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
    result = run_export(
        export_cfg,
        source_ply=ply,
        export_dir=paths.export_dir,
        runner=runner,
        render_dir=paths.train_dir / "renders",
        frames_dir=paths.kept_frames_dir if paths.kept_frames_dir.is_dir() else None,
        progress=progress,
    )
    artifacts = {"master_ply": str(result.master_ply), "web_ksplat": str(result.web_ksplat)}
    if result.thumbnail is not None:
        artifacts["thumbnail"] = str(result.thumbnail)
    return StageOutcome(artifacts=artifacts, metrics={}, message="Export .ply + .ksplat concluído.")


def handle_meshproxy(record: JobRecord, progress: Callable[[float, str], None]) -> StageOutcome:
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
        if exc.code == "OPEN3D_UNAVAILABLE":
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
    paths = job_paths(record.work_path)
    progress(0.1, "Estimando escala pela altura informada…")
    frames = record.stages["extracting"].artifacts.get("frames_dir") or str(paths.kept_frames_dir)
    result: AutocalResult = hook.run(
        AutocalContext(
            job_id=record.job_id,
            frames_dir=frames,
            user_height_m=record.user_height_m,
            registered_names=(),
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
