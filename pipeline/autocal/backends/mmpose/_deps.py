"""Optional MMPose / RTMPose import.

Approved exception to the workspace "no inline imports" rule. See
``autocal.backends.mediapipe._deps`` for the documented pattern:

- optional third-party import at **module top** with ``try/except``;
- ``AVAILABLE`` flag;
- backend module imports this file at the top and never imports mmpose/torch
  itself.

Never ``pip install mmpose`` / ``torch`` from the autocal workstream.
"""

from __future__ import annotations

from typing import Any

AVAILABLE: bool
MMPoseInferencer: Any

try:
    from mmpose.apis import MMPoseInferencer

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    MMPoseInferencer = None
