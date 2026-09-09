"""COLMAP CLI builders (feature_extractor → matcher → mapper → TXT convert)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sfm.config import CameraModel, ColmapConfig, ColmapPaths
from sfm.parse import count_input_images


# COLMAP 4.x moveu o toggle de GPU para os grupos FeatureExtraction/FeatureMatching;
# builds 3.x usam SiftExtraction.use_gpu / SiftMatching.use_gpu.
@dataclass(frozen=True)
class ColmapCliDialect:
    """Nomes de flag de GPU que o binário instalado aceita (None = omitir)."""

    extraction_gpu_flag: str | None = "SiftExtraction.use_gpu"
    matching_gpu_flag: str | None = "SiftMatching.use_gpu"


def _flag(value: bool) -> str:
    return "1" if value else "0"


def build_feature_extractor_command(
    config: ColmapConfig,
    paths: ColmapPaths,
    *,
    camera_model: CameraModel | None = None,
    gpu_flag: str | None = "SiftExtraction.use_gpu",
) -> list[str]:
    model = camera_model or config.camera_model
    argv = [
        config.colmap_bin,
        "feature_extractor",
        "--database_path",
        str(paths.database),
        "--image_path",
        str(paths.image_dir),
        "--ImageReader.single_camera",
        _flag(config.single_camera),
        "--ImageReader.camera_model",
        model,
    ]
    if gpu_flag is not None:
        argv += [f"--{gpu_flag}", _flag(config.use_gpu)]
    if config.sift_peak_threshold is not None:
        argv += ["--SiftExtraction.peak_threshold", f"{config.sift_peak_threshold:g}"]
    if config.sift_edge_threshold is not None:
        argv += ["--SiftExtraction.edge_threshold", f"{config.sift_edge_threshold:g}"]
    if config.sift_max_num_features is not None:
        argv += ["--SiftExtraction.max_num_features", str(config.sift_max_num_features)]
    return argv


def build_exhaustive_matcher_command(
    config: ColmapConfig,
    paths: ColmapPaths,
    *,
    gpu_flag: str | None = "SiftMatching.use_gpu",
) -> list[str]:
    argv = [
        config.colmap_bin,
        "exhaustive_matcher",
        "--database_path",
        str(paths.database),
    ]
    if gpu_flag is not None:
        argv += [f"--{gpu_flag}", _flag(config.use_gpu)]
    return argv


def build_sequential_matcher_command(
    config: ColmapConfig,
    paths: ColmapPaths,
    *,
    gpu_flag: str | None = "SiftMatching.use_gpu",
) -> list[str]:
    argv = [
        config.colmap_bin,
        "sequential_matcher",
        "--database_path",
        str(paths.database),
    ]
    if gpu_flag is not None:
        argv += [f"--{gpu_flag}", _flag(config.use_gpu)]
    argv += [
        "--SequentialMatching.overlap",
        str(config.sequential_overlap),
        "--SequentialMatching.quadratic_overlap",
        _flag(config.sequential_quadratic_overlap),
    ]
    return argv


def build_matcher_command(
    config: ColmapConfig,
    paths: ColmapPaths,
    matcher: Literal["exhaustive", "sequential"],
    *,
    gpu_flag: str | None = "SiftMatching.use_gpu",
) -> list[str]:
    if matcher == "exhaustive":
        return build_exhaustive_matcher_command(config, paths, gpu_flag=gpu_flag)
    if matcher == "sequential":
        return build_sequential_matcher_command(config, paths, gpu_flag=gpu_flag)
    raise AssertionError(f"unhandled matcher: {matcher!r}")


def build_mapper_command(config: ColmapConfig, paths: ColmapPaths) -> list[str]:
    return [
        config.colmap_bin,
        "mapper",
        "--database_path",
        str(paths.database),
        "--image_path",
        str(paths.image_dir),
        "--output_path",
        str(paths.sparse_dir),
        "--Mapper.min_model_size",
        str(config.min_registered_count),
        "--Mapper.multiple_models",
        _flag(config.mapper_multiple_models),
        "--Mapper.max_num_models",
        str(config.mapper_max_num_models),
        "--Mapper.init_num_trials",
        str(config.mapper_init_num_trials),
        "--Mapper.ba_global_max_num_iterations",
        str(config.mapper_ba_global_max_num_iterations),
    ]


def build_model_converter_txt_command(config: ColmapConfig, model_dir: Path) -> list[str]:
    return [
        config.colmap_bin,
        "model_converter",
        "--input_path",
        str(model_dir),
        "--output_path",
        str(model_dir),
        "--output_type",
        "TXT",
    ]


def build_sfm_pipeline_commands(
    config: ColmapConfig,
    paths: ColmapPaths,
    *,
    source_kind: Literal["video", "images"],
    dialect: ColmapCliDialect | None = None,
) -> list[list[str]]:
    dialect = dialect or ColmapCliDialect()
    image_count = count_input_images(paths.image_dir)
    matcher = config.resolve_matcher(source_kind, image_count=image_count)
    return [
        build_feature_extractor_command(config, paths, gpu_flag=dialect.extraction_gpu_flag),
        build_matcher_command(config, paths, matcher, gpu_flag=dialect.matching_gpu_flag),
        build_mapper_command(config, paths),
        build_model_converter_txt_command(config, paths.model_dir),
    ]
