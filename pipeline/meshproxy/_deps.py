"""Optional Open3D / NumPy import.

Approved exception to the workspace "no inline imports" rule: optional
third-party reconstruction stacks must not be imported from function bodies,
and must not fail the package import when the extra is missing.

Pattern (copy from ``autocal.backends.mediapipe._deps``):
1. This module is the *only* place that mentions ``open3d`` / ``numpy``.
2. ``try/except ImportError`` at **module top**.
3. ``AVAILABLE`` flag plus names bound to ``None`` on failure.
4. ``reconstruct`` imports *this* module at its own top and checks
   ``AVAILABLE`` before constructing native objects.

Never ``pip install open3d`` / ``numpy`` from the meshproxy workstream.
Open3D is heavy and GPU-optional; the module must import cleanly without it
and raise ``BackendUnavailableError`` only when reconstruction is executed.
"""

from __future__ import annotations

from typing import Any

AVAILABLE: bool
np: Any
o3d: Any

try:
    import numpy as np
    import open3d as o3d

    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    np = None
    o3d = None
