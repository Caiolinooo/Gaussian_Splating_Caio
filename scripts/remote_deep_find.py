"""Deeper leftover search: ply, ksplat, frames, old data dirs."""

from __future__ import annotations

import os

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"


def run(client: paramiko.SSHClient, command: str, timeout: int = 180) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    print("CMD", command[:140])
    print(text[-10000:])
    return text


def main() -> None:
    password = os.environ.get("GS_SSH_PASS")
    if not password:
        raise SystemExit("GS_SSH_PASS ausente")
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
    run(
        client,
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "keys=()\n"
        "for line in open('/home/caio/gaussian-splating/eval.env', encoding='utf-8'):\n"
        "    line=line.strip()\n"
        "    if not line or line.startswith('#') or '=' not in line: continue\n"
        "    k,_=line.split('=',1)\n"
        "    if 'PASS' in k or 'SECRET' in k or 'TOKEN' in k or 'KEY' in k: continue\n"
        "    print(k+'='+line.split('=',1)[1][:120])\n"
        "PY",
    )
    run(
        client,
        "echo '---PLY---'; find /home/caio /tmp /var/tmp -maxdepth 8 -type f "
        "\\( -iname '*.ply' -o -iname '*.ksplat' -o -iname 'points3D.txt' \\) 2>/dev/null | head -n 80; "
        "echo '---FRAMES---'; find /tmp /var/tmp /home/caio/gaussian-splating -maxdepth 6 "
        "-type d -iname 'frames' 2>/dev/null | head; "
        "echo '---OLD DATA---'; ls -la /home/caio/gaussian-data /home/caio/gs-data /opt/gs 2>/dev/null; "
        "ls -la /home/caio/gaussian-splating/var /home/caio/gaussian-splating/storage 2>/dev/null; "
        "echo '---START---'; sed -n '1,80p' /home/caio/gaussian-splating/start-api.sh",
    )
    client.close()


if __name__ == "__main__":
    main()
