"""Put the repo root on ``sys.path`` so ``import pipeline.meshproxy`` works.

Pytest may treat ``pipeline/pyproject.toml`` as rootdir (adding ``pipeline/``
to ``sys.path``). Inserting the monorepo root first keeps the namespace
package import stable.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
# parents: [0]=meshproxy, [1]=pipeline, [2]=raiz do monorepo.
_REPO_ROOT = _TESTS_DIR.parents[2]
for _path in (_REPO_ROOT, _TESTS_DIR):
    rendered = str(_path)
    if rendered not in sys.path:
        sys.path.insert(0, rendered)
