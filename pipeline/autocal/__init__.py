"""Auto-calibration by user height for Gaussian Splatting scenes.

Public entry point: ``run_auto_calibration`` → ``CalibrationResult``.
Pose backends (MediaPipe / MMPose) sit behind ``PoseBackend``; the Fase 1
benchmark chooses the default. Manual tape-measure calibration always
remains the confirmatory path (tasks.md §7).
"""

from __future__ import annotations

from autocal.backends import PoseBackend, PoseBackendName, create_pose_backend
from autocal.depth import ConstantDepthProvider, DepthProvider, HeuristicCameraDistanceProvider
from autocal.models import CalibrationResult
from autocal.service import run_auto_calibration
from autocal.types import FrameInput

__all__ = [
    "CalibrationResult",
    "ConstantDepthProvider",
    "DepthProvider",
    "FrameInput",
    "HeuristicCameraDistanceProvider",
    "PoseBackend",
    "PoseBackendName",
    "create_pose_backend",
    "run_auto_calibration",
]
__version__ = "0.2.0"
