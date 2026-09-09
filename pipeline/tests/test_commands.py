"""Generated CLI argv for ffmpeg, COLMAP, gsplat, splat-transform."""

from __future__ import annotations

from pathlib import Path

from export.commands import build_ksplat_command, build_thumbnail_command
from export.config import ExportConfig
from ingest.adaptive import format_fps
from ingest.probe import build_ffprobe_command
from ingest.video import build_ffmpeg_extract_command
from sfm.commands import (
    ColmapCliDialect,
    build_exhaustive_matcher_command,
    build_feature_extractor_command,
    build_mapper_command,
    build_model_converter_txt_command,
    build_sequential_matcher_command,
    build_sfm_pipeline_commands,
)
from sfm.config import ColmapConfig, ColmapPaths
from train.commands import build_simple_trainer_command
from train.config import TrainConfig


def test_ffprobe_command() -> None:
    argv = build_ffprobe_command("ffprobe", Path("/data/clip.mp4"))
    assert argv[:5] == ["ffprobe", "-v", "error", "-select_streams", "v:0"]
    assert "-of" in argv and "json" in argv
    assert argv[-1] == "/data/clip.mp4" or argv[-1].endswith("clip.mp4")


def test_ffmpeg_extract_command_uses_fps_and_even_scale() -> None:
    out = Path("/tmp/raw/frame_%06d.jpg")
    argv = build_ffmpeg_extract_command(
        "ffmpeg",
        Path("/data/clip.mp4"),
        out,
        fps=8.3333,
        max_edge=1600,
        jpeg_quality=2,
    )
    assert argv[0] == "ffmpeg"
    assert "-hide_banner" in argv and "-y" in argv
    assert argv[argv.index("-i") + 1].endswith("clip.mp4")
    vf = argv[argv.index("-vf") + 1]
    assert f"fps={format_fps(8.3333)}" in vf
    assert "min(1600,iw)" in vf
    assert "min(1600,ih)" in vf
    assert "force_original_aspect_ratio=decrease" in vf
    assert "trunc(iw/2)*2" in vf
    assert argv[argv.index("-q:v") + 1] == "2"
    assert argv[-1].endswith("frame_%06d.jpg")


def test_colmap_pipeline_video_uses_sequential_matcher() -> None:
    cfg = ColmapConfig(colmap_bin="colmap", matcher="auto", use_gpu=True, sequential_overlap=15)
    paths = ColmapPaths(image_dir=Path("/job/frames/kept"), work_dir=Path("/job/colmap"))
    commands = build_sfm_pipeline_commands(cfg, paths, source_kind="video")
    assert [item[1] for item in commands] == [
        "feature_extractor",
        "sequential_matcher",
        "mapper",
        "model_converter",
    ]
    feat = build_feature_extractor_command(cfg, paths)
    assert feat[0:2] == ["colmap", "feature_extractor"]
    assert "--database_path" in feat and str(paths.database) in feat
    assert "--image_path" in feat and str(paths.image_dir) in feat
    assert "--SiftExtraction.use_gpu" in feat
    assert feat[feat.index("--SiftExtraction.use_gpu") + 1] == "1"
    assert feat[feat.index("--ImageReader.single_camera") + 1] == "1"

    seq = build_sequential_matcher_command(cfg, paths)
    assert seq[1] == "sequential_matcher"
    assert seq[seq.index("--SequentialMatching.overlap") + 1] == "15"

    mapper = build_mapper_command(cfg, paths)
    assert mapper[1] == "mapper"
    assert mapper[mapper.index("--output_path") + 1] == str(paths.sparse_dir)
    assert mapper[mapper.index("--Mapper.multiple_models") + 1] == "1"
    assert mapper[mapper.index("--Mapper.max_num_models") + 1] == "8"
    assert mapper[mapper.index("--Mapper.init_num_trials") + 1] == "25"
    assert mapper[mapper.index("--Mapper.ba_global_max_num_iterations") + 1] == "25"
    assert mapper[mapper.index("--Mapper.min_model_size") + 1] == str(cfg.min_registered_count)

    conv = build_model_converter_txt_command(cfg, paths.model_dir)
    assert conv[1] == "model_converter"
    assert conv[conv.index("--output_type") + 1] == "TXT"


def test_colmap_images_use_exhaustive_matcher() -> None:
    cfg = ColmapConfig(matcher="auto")
    paths = ColmapPaths(image_dir=Path("images"), work_dir=Path("colmap"))
    commands = build_sfm_pipeline_commands(cfg, paths, source_kind="images")
    assert commands[1][1] == "exhaustive_matcher"
    exh = build_exhaustive_matcher_command(cfg, paths)
    assert "--SiftMatching.use_gpu" in exh


def test_colmap_large_image_set_uses_sequential(tmp_path) -> None:
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    for index in range(90):
        (image_dir / f"img_{index:03d}.jpg").write_bytes(b"x")
    cfg = ColmapConfig(matcher="auto", max_exhaustive_images=80)
    paths = ColmapPaths(image_dir=image_dir, work_dir=tmp_path / "colmap")
    commands = build_sfm_pipeline_commands(cfg, paths, source_kind="images")
    assert commands[1][1] == "sequential_matcher"


def test_gsplat_simple_trainer_command() -> None:
    cfg = TrainConfig(
        python_bin="python",
        trainer_script=Path("/opt/gsplat/examples/simple_trainer.py"),
        data_factor=4,
        max_steps=30_000,
        save_steps=(7_000, 30_000),
        eval_steps=(7_000, 30_000),
        ply_steps=(7_000, 30_000),
        save_ply=True,
        disable_viewer=True,
        disable_video=True,
    )
    argv = build_simple_trainer_command(
        cfg,
        data_dir=Path("/job/dataset"),
        result_dir=Path("/job/train"),
    )
    assert argv[0] == "python"
    assert argv[1].replace("\\", "/").endswith("simple_trainer.py")
    assert argv[2] == "default"
    assert argv[argv.index("--data_dir") + 1].replace("\\", "/").endswith("dataset")
    assert argv[argv.index("--data_factor") + 1] == "4"
    assert argv[argv.index("--result_dir") + 1].replace("\\", "/").endswith("train")
    assert argv[argv.index("--max_steps") + 1] == "30000"
    assert "--save_ply" in argv
    assert "--disable_viewer" in argv
    assert "--disable_video" in argv
    save_at = argv.index("--save_steps")
    assert argv[save_at + 1 : save_at + 3] == ["7000", "30000"]


def test_gsplat_ckpt_eval_flag() -> None:
    argv = build_simple_trainer_command(
        TrainConfig(),
        data_dir=Path("data"),
        result_dir=Path("out"),
        ckpt=Path("out/ckpts/ckpt_6999_rank0.pt"),
    )
    assert "--ckpt" in argv
    assert argv[argv.index("--ckpt") + 1].endswith("ckpt_6999_rank0.pt")


def test_splat_transform_ksplat_command() -> None:
    cfg = ExportConfig(
        splat_transform_bin="splat-transform",
        filter_nan=True,
        filter_floaters=True,
        floater_voxel=0.05,
        floater_opacity=0.1,
        floater_min_contribution=0.004,
        web_sh_degree=2,
    )
    argv = build_ksplat_command(cfg, Path("/job/export/master.ply"), Path("/job/export/scene.ksplat"))
    assert argv[0] == "splat-transform"
    assert argv[1].endswith("master.ply")
    assert "--filter-nan" in argv
    assert "--filter-floaters" in argv
    assert argv[argv.index("--filter-floaters") + 1] == "0.05,0.1,0.004"
    assert argv[argv.index("--filter-harmonics") + 1] == "2"
    assert argv[-1].endswith("scene.ksplat")


def test_colmap_v4_dialect_gpu_flags() -> None:
    cfg = ColmapConfig(use_gpu=True)
    paths = ColmapPaths(image_dir=Path("/job/images"), work_dir=Path("/job/colmap"))
    dialect = ColmapCliDialect(
        extraction_gpu_flag="FeatureExtraction.use_gpu",
        matching_gpu_flag="FeatureMatching.use_gpu",
    )
    commands = build_sfm_pipeline_commands(cfg, paths, source_kind="video", dialect=dialect)
    extractor = commands[0]
    assert "--FeatureExtraction.use_gpu" in extractor
    assert "--SiftExtraction.use_gpu" not in extractor
    matcher = commands[1]
    assert "--FeatureMatching.use_gpu" in matcher
    assert "--SiftMatching.use_gpu" not in matcher


def test_colmap_dialect_none_omits_gpu_flags() -> None:
    cfg = ColmapConfig(use_gpu=False)
    paths = ColmapPaths(image_dir=Path("/job/images"), work_dir=Path("/job/colmap"))
    dialect = ColmapCliDialect(extraction_gpu_flag=None, matching_gpu_flag=None)
    commands = build_sfm_pipeline_commands(cfg, paths, source_kind="video", dialect=dialect)
    assert all("use_gpu" not in " ".join(argv) for argv in commands[:2])


def test_thumbnail_command() -> None:
    argv = build_thumbnail_command("ffmpeg", Path("src.png"), Path("thumb.jpg"), max_edge=512)
    assert argv[0] == "ffmpeg"
    assert "-vf" in argv
    assert "512" in argv[argv.index("-vf") + 1]
    assert argv[-1].endswith("thumb.jpg")
