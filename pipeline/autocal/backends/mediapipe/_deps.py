"""Optional MediaPipe Tasks import.

Approved exception to the workspace "no inline imports" rule: optional
third-party pose stacks must not be imported from function bodies, and must
not fail the package import when the extra is missing.

Pattern (copy for any new backend):
1. This module is the *only* place that mentions ``mediapipe``.
2. ``try/except ImportError`` at **module top**.
3. ``AVAILABLE`` flag plus names bound to ``None`` on failure.
4. ``MediaPipePoseBackend`` imports *this* module at its own top and checks
   ``AVAILABLE`` before constructing native objects.

Never ``pip install mediapipe`` from the autocal workstream.
"""

from __future__ import annotations

from typing import Any

AVAILABLE: bool
mp: Any
np: Any
BaseOptions: Any
PoseLandmarker: Any
PoseLandmarkerOptions: Any
RunningMode: Any

try:
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks.python.core.base_options import BaseOptions
    from mediapipe.tasks.python.vision.pose_landmarker import (
        PoseLandmarker,
        PoseLandmarkerOptions,
    )

    try:
        from mediapipe.tasks.python.vision.core.vision_task_running_mode import (
            VisionTaskRunningMode as RunningMode,
        )
    except ImportError:  # older Tasks layout
        from mediapipe.tasks.python.vision import RunningMode  # type: ignore[attr-defined]

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    mp = None
    np = None
    BaseOptions = None
    PoseLandmarker = None
    PoseLandmarkerOptions = None
    RunningMode = None
