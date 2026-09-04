"""Put ``pipeline/`` on ``sys.path`` so tests import the ``autocal`` package."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("pydantic")

_TESTS_DIR = Path(__file__).resolve().parent
_PIPELINE_ROOT = _TESTS_DIR.parents[1]
for _path in (_PIPELINE_ROOT, _TESTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
