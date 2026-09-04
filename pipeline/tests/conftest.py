"""Put ``pipeline/`` on ``sys.path`` so ingest/sfm/train/export/jobs/provisioner import."""

from __future__ import annotations

import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
root = str(PIPELINE_ROOT)
if root not in sys.path:
    sys.path.insert(0, root)
