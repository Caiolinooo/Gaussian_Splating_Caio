"""COLMAP CLI builders (feature_extractor → matcher → mapper → TXT convert)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from sfm.config import CameraModel, ColmapConfig, ColmapPaths


def _flag(value: bool) -> str:
    return "1" if value else "0"


def build_feature_extractor_command(
    config: ColmapConfig,
    paths: ColmapPaths,
    *,
    camera_model: CameraModel | None = None,
) -> list[str]:
    model = camera_model or config.camera_model
    return [
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
        "--SiftExtraction.use_gpu",
        _flag(config.use_gpu),
    ]


def build_exhaustive_matcher_command(config: ColmapConfig, paths: ColmapPaths) -> list[str]:
    return [
        config.colmap_bin,
        "exhaustive_matcher",
        "--database_path",
        str(paths.database),
        "--SiftMatching.use_gpu",
        _flag(config.use_gpu),
    ]


def build_sequential_matcher_command(config: ColmapConfig, paths: ColmapPaths) -> list[str]:
    return [
        config.colmap_bin,
        "sequential_matcher",
        "--database_path",
        str(paths.database),
        "--SiftMatching.use_gpu",
        _flag(config.use_gpu),
        "--SequentialMatching.overlap",
        str(config.sequential_overlap),
        "--SequentialMatching.quadratic_overlap",
        _flag(config.sequential_quadratic_overlap),
    ]


def build_matcher_command(
    config: ColmapConfig,
    paths: ColmapPaths,
    matcher: Literal["exhaustive", "sequential"],
) -> list[str]:
    if matcher == "exhaustive":
        return build_exhaustive_matcher_command(config, paths)
    if matcher == "sequential":
        return build_sequential_matcher_command(config, paths)
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
) -> list[list[str]]:
    matcher = config.resolve_matcher(source_kind)
    return [
        build_feature_extractor_command(config, paths),
        build_matcher_command(config, paths, matcher),
        build_mapper_command(config, paths),
        build_model_converter_txt_command(config, paths.model_dir),
    ]
