"""Upload quality/viewer files to the L4 host. Password via GS_SSH_PASS only."""

from __future__ import annotations

import os
import posixpath
from pathlib import Path

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"
REMOTE_ROOT = "/home/caio/gaussian-splating"
ROOT = Path(__file__).resolve().parents[1]

SOURCE_FILES = [
    "pipeline/jobs/handlers.py",
    "pipeline/jobs/machine.py",
    "pipeline/jobs/quality.py",
    "pipeline/jobs/states.py",
    "pipeline/jobs/store.py",
    "pipeline/jobs/autocal.py",
    "pipeline/jobs/autocal_adapter.py",
    "pipeline/jobs/__init__.py",
    "pipeline/relight/__init__.py",
    "pipeline/relight/sh_env.py",
    "pipeline/temporal/__init__.py",
    "pipeline/temporal/clusters.py",
    "pipeline/temporal/flow_rigs.py",
    "pipeline/ingest/config.py",
    "pipeline/geom/__init__.py",
    "pipeline/geom/planes.py",
    "pipeline/autocal/colmap_depth.py",
    "pipeline/sfm/config.py",
    "pipeline/sfm/commands.py",
    "pipeline/sfm/runner.py",
    "pipeline/train/config.py",
    "pipeline/train/runner.py",
    "pipeline/export/config.py",
    "pipeline/sceneio/document.py",
    "pipeline/sceneio/export.py",
    "apps/api/app/core/config.py",
    "apps/api/app/services/job_runtime.py",
    "apps/api/app/services/job_supervisor.py",
    "apps/api/app/routers/jobs.py",
    "apps/api/.env.example",
    "scripts/make_textured_room.py",
    "packages/viewer/src/index.ts",
    "packages/viewer/src/relight/shEnv.ts",
    "packages/viewer/src/temporal/cameras.ts",
    "packages/viewer/src/renderer/SplatRenderer.ts",
    "packages/viewer/src/renderer/SparkBackend.ts",
    "packages/viewer/src/renderer/MkKelloggBackend.ts",
    "packages/viewer/src/renderer/sparkAdapter.ts",
    "packages/viewer/src/renderer/splatFrame.ts",
    "packages/viewer/src/editing/sceneSchema.ts",
    "packages/viewer/src/editing/serialize.ts",
]

TREE_DIRS = (
    "packages/viewer/dist",
    "apps/web/src",
    "apps/web/dist",
)


def collect() -> list[Path]:
    files: list[Path] = []
    for rel in SOURCE_FILES:
        path = ROOT / rel
        if path.is_file():
            files.append(path)
    for folder in TREE_DIRS:
        base = ROOT / folder
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and "node_modules" not in path.parts:
                files.append(path)
    return files


def mkdir_p(sftp: paramiko.SFTPClient, path: str) -> None:
    parts = path.strip("/").split("/")
    current = ""
    for part in parts:
        current += "/" + part
        try:
            sftp.stat(current)
        except FileNotFoundError:
            try:
                sftp.mkdir(current)
            except OSError:
                pass


def run(client: paramiko.SSHClient, command: str, timeout: int = 90) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    print("CMD", command[:140])
    print(text[-2500:])
    return text


def main() -> None:
    password = os.environ.get("GS_SSH_PASS")
    if not password:
        raise SystemExit("GS_SSH_PASS ausente")
    files = collect()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        HOST,
        username=USER,
        password=password,
        timeout=30,
        look_for_keys=False,
        allow_agent=False,
    )
    sftp = client.open_sftp()
    uploaded = 0
    for local in files:
        rel = local.relative_to(ROOT).as_posix()
        remote = f"{REMOTE_ROOT}/{rel}"
        mkdir_p(sftp, posixpath.dirname(remote))
        sftp.put(str(local), remote)
        uploaded += 1
    sftp.close()
    print("uploaded", uploaded)
    run(
        client,
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "import re\n"
        "p = Path('/home/caio/gaussian-splating/eval.env')\n"
        "text = p.read_text()\n"
        "pairs = {\n"
        "    'TRAIN_MAX_STEPS': '30000',\n"
        "    'TRAIN_DATA_FACTOR': '2',\n"
        "    'TRAIN_SH_DEGREE': '3',\n"
        "    'COLMAP_MAX_EXHAUSTIVE_IMAGES': '220',\n"
        "}\n"
        "for key, value in pairs.items():\n"
        "    if re.search(rf'^{key}=', text, re.M):\n"
        "        text = re.sub(rf'^{key}=.*$', f'{key}={value}', text, flags=re.M)\n"
        "    else:\n"
        "        text += f'\\n{key}={value}\\n'\n"
        "p.write_text(text)\n"
        "print('env-ok')\n"
        "for key in pairs:\n"
        "    for line in text.splitlines():\n"
        "        if line.startswith(key + '='):\n"
        "            print(line)\n"
        "PY",
    )
    run(client, "ps aux | grep -E 'uvicorn|app.main' | grep -v grep")
    client.close()


if __name__ == "__main__":
    main()
