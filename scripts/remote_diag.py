"""Diagnose remote uvicorn routes without printing secrets."""

from __future__ import annotations

import os

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"


def run(client: paramiko.SSHClient, command: str, timeout: int = 60) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    print("CMD", command[:200])
    print(text[-6000:])
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
    run(client, "ps aux | grep -E 'uvicorn|python' | grep -v grep | head -n 30")
    run(client, "ss -lntp | grep 2222 || netstat -lntp | grep 2222 || true")
    run(
        client,
        "cd /home/caio/gaussian-splating && "
        "ls -la eval.env start-api.sh apps/api/app/main.py apps/api/app/routers 2>&1 | head -n 40; "
        "echo '---ROUTES---'; "
        "rg -n 'rebuild|auth/login|include_router' apps/api/app -g '*.py' | head -n 40; "
        "echo '---LOG---'; "
        "ls -lt *.log 2>/dev/null | head; "
        "tail -n 80 eval-2222.log 2>/dev/null; "
        "tail -n 80 /home/caio/gaussian-splating/eval-2222.log 2>/dev/null; "
        "ls /tmp/*2222* /tmp/uvicorn* 2>/dev/null; "
        "echo '---CURL---'; "
        "curl -sS -m 8 -o /tmp/h.txt -w 'health:%{http_code}\\n' http://127.0.0.1:2222/health || true; "
        "curl -sS -m 8 -o /tmp/s.txt -w 'setup:%{http_code}\\n' http://127.0.0.1:2222/setup || true; "
        "curl -sS -m 8 -o /tmp/r.txt -w 'openapi:%{http_code}\\n' http://127.0.0.1:2222/openapi.json || true; "
        "curl -sS -m 8 -o /tmp/a.txt -w 'auth:%{http_code}\\n' -X POST http://127.0.0.1:2222/auth/login -H 'Content-Type: application/json' -d '{}' || true; "
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "for name in ['h','s','r','a']:\n"
        "    p=Path(f'/tmp/{name}.txt')\n"
        "    if p.exists():\n"
        "        print(name, p.read_text(encoding='utf-8', errors='replace')[:800])\n"
        "PY",
    )
    run(
        client,
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "p=Path('/proc/523657/environ')\n"
        "if p.exists():\n"
        "    env=p.read_bytes().split(b'\\x00')\n"
        "    keys=[e.decode('utf-8','replace') for e in env if e.startswith(b'TRAIN_') or e.startswith(b'COLMAP_') or e.startswith(b'PYTHON') or e.startswith(b'LOCAL_AUTH_USER')]\n"
        "    print('\\n'.join(keys))\n"
        "else:\n"
        "    print('pid gone')\n"
        "PY",
    )
    client.close()


if __name__ == "__main__":
    main()
