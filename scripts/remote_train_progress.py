"""Inspect remote trainer files. Password via GS_SSH_PASS only."""

from __future__ import annotations

import os

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
set -e
echo '---PS TRAIN---'
ps -p 542420 -o pid,etime,pcpu,pmem,cmd --no-headers || echo DEAD
echo '---GPU---'
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
echo '---TRAIN TREE---'
ls -la {ROOT}/train 2>/dev/null | head -n 40
echo '---STATS---'
find {ROOT}/train -type f \\( -name '*.json' -o -name '*.txt' -o -name '*.log' -o -name '*.ply' -o -name '*.pt' \\) -printf '%T+ %s %p\\n' 2>/dev/null | sort | tail -n 40
echo '---TB---'
find {ROOT}/train -name 'events.out.tfevents*' -printf '%T+ %s %p\\n' 2>/dev/null | tail
echo '---STATS JSON---'
python3 - <<'PY'
import json, os, glob
root = '{ROOT}/train/stats'
for p in sorted(glob.glob(os.path.join(root, '*.json'))):
    data = json.load(open(p, encoding='utf-8'))
    print(os.path.basename(p), data)
print('---LOG TAIL---')
log = '{ROOT}/train/train.log'
print(open(log, encoding='utf-8', errors='replace').read()[-1200:])
PY
"""
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=60, get_pty=True)
    print(stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace"))
    client.close()


if __name__ == "__main__":
    main()
