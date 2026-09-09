"""Find leftover videos and job workdirs on the L4 host."""

from __future__ import annotations

import os

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"


def run(client: paramiko.SSHClient, command: str, timeout: int = 120) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    print("CMD", command[:160])
    print(text[-9000:])
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
        "echo '---CAIO---'; ls -la /home/caio/gaussian-splating/data/caio; "
        "echo '---SQLITE---'; "
        "python3 - <<'PY'\n"
        "import sqlite3\n"
        "from pathlib import Path\n"
        "p=Path('/home/caio/gaussian-splating/data/pipeline-jobs.sqlite')\n"
        "print('exists', p.exists(), 'size', p.stat().st_size if p.exists() else 0)\n"
        "if p.exists():\n"
        "    con=sqlite3.connect(p)\n"
        "    print(con.execute('select count(*) from jobs').fetchone())\n"
        "    for row in con.execute('select job_id, state, substr(payload,1,200) from jobs'):\n"
        "        print(row[0], row[1], row[2][:180])\n"
        "PY",
    )
    run(
        client,
        "echo '---VIDEOS---'; "
        "find /home/caio/gaussian-splating /home/caio -maxdepth 6 "
        "-type f \\( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' -o -iname '*.webm' \\) "
        "2>/dev/null | head -n 80; "
        "echo '---WORK---'; "
        "find /home/caio/gaussian-splating /tmp /var/tmp -maxdepth 5 -type d -iname '*cf9a*' 2>/dev/null; "
        "ls -la /home/caio/gaussian-splating/data/caio 2>/dev/null; "
        "find /home/caio/gaussian-splating/data -maxdepth 4 -type d 2>/dev/null | head -n 80",
    )
    client.close()


if __name__ == "__main__":
    main()
