"""Apply current L4 quality defaults onto an existing job record."""

from __future__ import annotations

from dataclasses import replace

from export.config import ExportConfig
from ingest.config import VideoIngestConfig
from jobs.models import JobRecord
from sfm.config import ColmapConfig
from train.config import TrainConfig


def apply_quality_defaults(record: JobRecord) -> JobRecord:
    train = TrainConfig()
    record.train = replace(
        record.train,
        data_factor=train.data_factor,
        max_steps=train.max_steps,
        save_steps=train.save_steps,
        eval_steps=train.eval_steps,
        ply_steps=train.ply_steps,
        extra_args=train.extra_args,
        disable_video=True,
        save_ply=True,
    )
    colmap = ColmapConfig()
    record.colmap = replace(
        record.colmap,
        sequential_overlap=colmap.sequential_overlap,
        sequential_quadratic_overlap=colmap.sequential_quadratic_overlap,
        max_exhaustive_images=colmap.max_exhaustive_images,
        min_registered_ratio=colmap.min_registered_ratio,
        sift_peak_threshold=colmap.sift_peak_threshold,
        sift_edge_threshold=colmap.sift_edge_threshold,
        sift_max_num_features=colmap.sift_max_num_features,
        mapper_multiple_models=colmap.mapper_multiple_models,
        mapper_max_num_models=colmap.mapper_max_num_models,
        mapper_init_num_trials=colmap.mapper_init_num_trials,
    )
    export = ExportConfig()
    record.export = replace(record.export, web_sh_degree=export.web_sh_degree)
    video = VideoIngestConfig()
    record.video_ingest = replace(
        record.video_ingest,
        target_min_frames=video.target_min_frames,
        target_max_frames=video.target_max_frames,
        max_edge_px=video.max_edge_px,
    )
    return record
