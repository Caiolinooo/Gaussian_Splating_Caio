"""Dump train/export stats as ASCII. Password via GS_SSH_PASS."""

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
import json, os, glob
root = {ROOT!r}
print('STATS')
for p in sorted(glob.glob(root + '/train/stats/*.json')):
    data = json.load(open(p, encoding='utf-8'))
    print(os.path.basename(p), json.dumps(data, ensure_ascii=True))
print('PLY')
for p in sorted(glob.glob(root + '/train/ply/*.ply') + glob.glob(root + '/export/*.ply') + glob.glob(root + '/export/*')):
    if os.path.isfile(p):
        print(os.path.getmtime(p), os.path.getsize(p), p.replace(root+'/',''))
print('SPARSE')
for p in sorted(glob.glob(root + '/colmap/sparse/*/points3D.txt') + glob.glob(root + '/colmap/sparse/*/images.txt')):
    n = sum(1 for line in open(p, encoding='utf-8', errors='replace') if line.strip() and not line.startswith('#'))
    print(n, p.replace(root+'/',''))
print('TEMPORAL')
for name in ('export/temporal.json','export/relight.json'):
    p = os.path.join(root, name)
    if os.path.isfile(p):
        data = json.load(open(p, encoding='utf-8'))
        if isinstance(data, dict):
            print(name, 'keys', list(data)[:16], 'n_cam', len(data.get('cameras') or data.get('frames') or []))
        else:
            print(name, type(data).__name__)
PY
"""
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=60, get_pty=True)
    text = stdout.read().decode("ascii", "replace") + stderr.read().decode("ascii", "replace")
    sys.stdout.buffer.write(text.encode("ascii", "replace"))
    client.close()


if __name__ == "__main__":
    main()
