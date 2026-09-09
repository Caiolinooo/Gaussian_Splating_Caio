"""Copy numeric-latest train ply over stale export/master.ply. GS_SSH_PASS only."""

from __future__ import annotations

import os
import sys

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"
JOB = "3ce6fee7-a665-450d-990f-2284331fe5e6"
ROOT = f"/home/caio/gaussian-splating/data/caio/{JOB}"


def main() -> None:
    password = os.environ.get("GS_SSH_PASS")
    if not password:
        raise SystemExit("GS_SSH_PASS ausente")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=30, look_for_keys=False, allow_agent=False)
    cmd = f"""
python3 - <<'PY'
import os, shutil, glob
root = {ROOT!r}
ply_dir = os.path.join(root, 'train', 'ply')
cands = []
for p in glob.glob(os.path.join(ply_dir, 'point_cloud_*.ply')):
    stem = os.path.splitext(os.path.basename(p))[0]
    step = -1
    for part in reversed(stem.split('_')):
        if part.isdigit():
            step = int(part)
            break
    cands.append((step, os.path.getmtime(p), p))
cands.sort()
src = cands[-1][2]
dst = os.path.join(root, 'export', 'master.ply')
print('SRC', cands[-1][0], os.path.getsize(src), src)
print('DST_BEFORE', os.path.getsize(dst) if os.path.isfile(dst) else 0)
shutil.copy2(src, dst)
print('DST_AFTER', os.path.getsize(dst))
PY
"""
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=60, get_pty=True)
    sys.stdout.buffer.write(stdout.read() + stderr.read())
    client.close()


if __name__ == "__main__":
    main()
