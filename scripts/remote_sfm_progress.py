"""Check whether remote COLMAP rebuild is alive. Password via GS_SSH_PASS."""

from __future__ import annotations

import os

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"
JOB = "3ce6fee7-a665-450d-990f-2284331fe5e6"


def main() -> None:
    password = os.environ.get("GS_SSH_PASS")
    if not password:
        raise SystemExit("GS_SSH_PASS ausente")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=30, look_for_keys=False, allow_agent=False)
    cmd = (
        "ps aux | grep -E 'colmap|uvicorn app.main|simple_trainer' | grep -v grep | head -n 20; "
        "echo '---GPU---'; "
        "nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null | head; "
        f"echo '---LOGS---'; "
        f"ROOT=/home/caio/gaussian-splating/data/caio/{JOB}; "
        "find \"$ROOT\" -name '*.log' -printf '%T@ %p\\n' 2>/dev/null | sort -n | tail -n 8; "
        "echo '---COLMAP TAIL---'; "
        "LOG=$(find \"$ROOT\" -name 'colmap.log' | head -n 1); "
        "if [ -n \"$LOG\" ]; then echo FILE $LOG; tail -n 30 \"$LOG\"; fi; "
        "echo '---MATCHER---'; "
        "rg -n 'exhaustive|sequential|matcher' \"$ROOT\"/logs \"$ROOT\"/colmap -g '*.log' 2>/dev/null | tail -n 20"
    )
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=60, get_pty=True)
    print(stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace"))
    client.close()


if __name__ == "__main__":
    main()
