"""Promote the triangulated sparse model and retrain. Password via GS_SSH_PASS."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"
JOB = "3ce6fee7-a665-450d-990f-2284331fe5e6"
ROOT = Path(__file__).resolve().parents[1]


def run(client: paramiko.SSHClient, command: str, timeout: int = 180) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    sys.stdout.buffer.write(text.encode("utf-8", "replace"))
    return text


def main() -> None:
    password = os.environ.get("GS_SSH_PASS")
    if not password:
        raise SystemExit("GS_SSH_PASS ausente")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=30, look_for_keys=False, allow_agent=False)
    sftp = client.open_sftp()
    sftp.put(str(ROOT / "pipeline/sfm/parse.py"), "/home/caio/gaussian-splating/pipeline/sfm/parse.py")
    sftp.put(str(ROOT / "pipeline/sfm/runner.py"), "/home/caio/gaussian-splating/pipeline/sfm/runner.py")
    sftp.close()
    run(
        client,
        "cd /home/caio/gaussian-splating && PYTHONPATH=pipeline .venv/bin/python - <<'PY'\n"
        "from pathlib import Path\n"
        "from sfm.parse import pick_largest_model, score_reconstruction\n"
        "from sfm.runner import promote_sparse_model\n"
        f"sparse = Path('/home/caio/gaussian-splating/data/caio/{JOB}/colmap/sparse')\n"
        "best = pick_largest_model(sparse)\n"
        "print('best', best, score_reconstruction(best) if best else None)\n"
        "if best is not None:\n"
        "    dest = promote_sparse_model(sparse, best)\n"
        "    print('promoted', dest, score_reconstruction(dest))\n"
        f"link = Path('/home/caio/gaussian-splating/data/caio/{JOB}/dataset/sparse')\n"
        "print('link', link, '->', link.resolve() if link.exists() else None)\n"
        "PY",
    )
    client.close()


if __name__ == "__main__":
    main()
