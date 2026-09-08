"""On-disk layout of a single job working directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class JobPaths:
    root: Path

    @property
    def state_file(self) -> Path:
        return self.root / "job.json"

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def frames_dir(self) -> Path:
        return self.root / "frames"

    @property
    def kept_frames_dir(self) -> Path:
        return self.frames_dir / "kept"

    @property
    def images_versions_dir(self) -> Path:
        return self.input_dir / "images"

    @property
    def colmap_dir(self) -> Path:
        return self.root / "colmap"

    @property
    def colmap_db(self) -> Path:
        return self.colmap_dir / "database.db"

    @property
    def colmap_sparse(self) -> Path:
        return self.colmap_dir / "sparse"

    @property
    def dataset_dir(self) -> Path:
        return self.root / "dataset"

    @property
    def train_dir(self) -> Path:
        return self.root / "train"

    @property
    def export_dir(self) -> Path:
        return self.root / "export"

    @property
    def master_ply(self) -> Path:
        return self.export_dir / "master.ply"

    @property
    def web_ksplat(self) -> Path:
        return self.export_dir / "scene.ksplat"

    @property
    def calibration_json(self) -> Path:
        return self.export_dir / "calibration.json"

    @property
    def scene_json(self) -> Path:
        return self.export_dir / "scene.json"

    @property
    def scene_package(self) -> Path:
        return self.export_dir / "scene.zip"

    @property
    def thumbnails_dir(self) -> Path:
        return self.export_dir / "thumbnails"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    def ensure(self) -> None:
        for path in (
            self.root,
            self.input_dir,
            self.frames_dir,
            self.colmap_dir,
            self.dataset_dir,
            self.train_dir,
            self.export_dir,
            self.logs_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


def job_paths(work_dir: Path | str) -> JobPaths:
    return JobPaths(root=Path(work_dir))
