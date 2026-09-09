"""Restart remote uvicorn with current eval.env. Password via GS_SSH_PASS."""

from __future__ import annotations

import os

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"


def run(client: paramiko.SSHClient, command: str, timeout: int = 180) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    print("CMD", command[:180])
    print(text[-4000:])
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
    run(client, "pkill -f 'uvicorn app.main:app' || true; sleep 2; ps aux | grep 'uvicorn app.main' | grep -v grep || true")
    run(
        client,
        "cd /home/caio/gaussian-splating && "
        "nohup bash -lc 'set -a; source eval.env; set +a; "
        "exec .venv/bin/python -m uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 2222' "
        ">> /home/caio/gaussian-splating/eval-2222.log 2>&1 < /dev/null & "
        "sleep 5; "
        "ps aux | grep 'uvicorn app.main' | grep -v grep; "
        "curl -sS -m 8 -o /dev/null -w 'health:%{http_code}\\n' http://127.0.0.1:2222/health; "
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "import os\n"
        "pids=[]\n"
        "for line in os.popen(\"ps aux\").read().splitlines():\n"
        "    if 'uvicorn app.main' in line and 'grep' not in line:\n"
        "        pids.append(line.split()[1])\n"
        "print('pids', pids)\n"
        "for pid in pids:\n"
        "    env=Path(f'/proc/{pid}/environ').read_bytes().split(b'\\x00')\n"
        "    for item in env:\n"
        "        if item.startswith(b'TRAIN_') or item.startswith(b'COLMAP_MAX'):\n"
        "            print(item.decode())\n"
        "PY",
    )
    client.close()


if __name__ == "__main__":
    main()
