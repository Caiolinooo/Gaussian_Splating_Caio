"""Public input types for the auto-calibration service.

``pipeline/ingest`` should produce ``FrameInput`` after ffmpeg extraction
(or after a multi-image upload). This module does **not** import ingest —
the jobs orchestrator copies the documented fields across the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from autocal.backends.base import PersonPose


@dataclass
class FrameInput:
    """One RGB frame plus optional precomputed poses (used by tests).

    Attributes
    ----------
    frame_id:
        Stable id; must match COLMAP image names when a ``DepthProvider``
        looks up per-view depth / intrinsics.
    width, height:
        Pixel resolution. Required even when ``image`` is omitted.
    image:
        Optional RGB ``uint8`` array ``(H, W, 3)``. Needed only when a live
        ``PoseBackend`` must run (not for synthetic tests).
    poses:
        If set (even to ``[]``), the service **skips** the pose backend for
        this frame and uses these detections.
    """

    frame_id: str
    width: int
    height: int
    image: Any | None = None
    poses: list[PersonPose] | None = field(default=None)
