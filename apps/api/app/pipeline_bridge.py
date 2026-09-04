"""Put ``pipeline/`` on ``sys.path`` so ``from jobs import ...`` works.

The insert happens **once** at module import time (guarded by
``sys._gs_pipeline_on_path``). ``PIPELINE_PATH`` defaults to
``../../pipeline`` resolved from ``apps/api`` — not from the process cwd.

Production / WSL2 deploy should prefer an editable install of the pipeline
package instead of this path hack::

    pip install -e ./pipeline

Note: the current ``pipeline/pyproject.toml`` only exports ``provisioner``.
Until ``jobs`` (and ingest/sfm/train/export) are declared as packages there,
this bridge remains the supported way for the API to import ``jobs``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.core.config import settings

_PATH_FLAG = "_gs_pipeline_on_path"


def _resolve_pipeline_path() -> Path:
    return settings.resolved_pipeline_path()


_PIPELINE_PATH = _resolve_pipeline_path()

# Insert exactly once. Subsequent imports of this module are no-ops.
if not getattr(sys, _PATH_FLAG, False):
    resolved = str(_PIPELINE_PATH)
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    setattr(sys, _PATH_FLAG, True)


def pipeline_path() -> Path:
    return _PIPELINE_PATH
