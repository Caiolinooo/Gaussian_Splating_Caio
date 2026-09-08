"""Find or fetch gsplat ``examples/simple_trainer.py`` without compiling COLMAP."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from provisioner.bins import resolve_simple_trainer

GSPLAT_REPO = "https://github.com/nerfstudio-project/gsplat.git"


def default_examples_root() -> Path:
    return Path.home() / "gaussian-splating" / "vendor" / "gsplat-examples"


def ensure_simple_trainer(log=print) -> str:
    existing = resolve_simple_trainer("simple_trainer.py")
    if Path(existing).is_file():
        log(f"simple_trainer.py já existe: {existing}")
        return existing

    dest = default_examples_root()
    trainer = dest / "examples" / "simple_trainer.py"
    if trainer.is_file():
        return str(trainer)

    git = shutil.which("git")
    if git is None:
        log("git ausente — não baixei examples/simple_trainer.py.")
        return existing

    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        log(f"Clonando examples do gsplat em {dest}…")
        clone = subprocess.run(
            [git, "clone", "--depth", "1", "--filter=blob:none", "--sparse", GSPLAT_REPO, str(dest)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        if clone.returncode != 0:
            log((clone.stderr or clone.stdout or "git clone falhou").strip()[:400])
            return existing
        sparse = subprocess.run(
            [git, "-C", str(dest), "sparse-checkout", "set", "examples"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        if sparse.returncode != 0:
            log((sparse.stderr or sparse.stdout or "sparse-checkout falhou").strip()[:400])
    if trainer.is_file():
        log(f"simple_trainer.py baixado: {trainer}")
        return str(trainer)
    return existing
