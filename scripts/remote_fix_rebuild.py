"""Upload SfM matcher fix, restart API, rebuild the live office job."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"
ROOT = Path(__file__).resolve().parents[1]
JOB = "3ce6fee7-a665-450d-990f-2284331fe5e6"


def run(client: paramiko.SSHClient, command: str, timeout: int = 180) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    print("CMD", command[:160])
    print(text[-3500:])
    return text


def main() -> None:
    password = os.environ.get("GS_SSH_PASS")
    if not password:
        raise SystemExit("GS_SSH_PASS ausente")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=30, look_for_keys=False, allow_agent=False)
    sftp = client.open_sftp()
    sftp.put(str(ROOT / "pipeline/sfm/runner.py"), "/home/caio/gaussian-splating/pipeline/sfm/runner.py")
    sftp.close()
    run(client, "pkill -f 'uvicorn app.main:app' || true; sleep 2")
    run(
        client,
        "cd /home/caio/gaussian-splating && "
        "nohup bash -lc 'set -a; source eval.env; set +a; "
        "exec .venv/bin/python -m uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 2222' "
        ">> /home/caio/gaussian-splating/eval-2222.log 2>&1 < /dev/null & sleep 5; "
        "curl -sS -m 8 -o /dev/null -w 'health:%{http_code}\\n' http://127.0.0.1:2222/health",
    )
    run(
        client,
        "python3 - <<'PY'\n"
        "import json, urllib.error, urllib.request\n"
        f"job='{JOB}'\n"
        "env={}\n"
        "for line in open('/home/caio/gaussian-splating/eval.env', encoding='utf-8'):\n"
        "    line=line.strip()\n"
        "    if not line or line.startswith('#') or '=' not in line: continue\n"
        "    k,v=line.split('=',1); env[k]=v\n"
        "req=urllib.request.Request('http://127.0.0.1:2222/auth/login', data=json.dumps({'username':env.get('LOCAL_AUTH_USER','caio'),'password':env.get('LOCAL_AUTH_PASSWORD','')}).encode(), headers={'Content-Type':'application/json'})\n"
        "token=json.loads(urllib.request.urlopen(req, timeout=20).read())['access_token']\n"
        "req=urllib.request.Request(f'http://127.0.0.1:2222/jobs/{job}/rebuild?from_stage=sfm', method='POST', headers={'Authorization': f'Bearer {token}'})\n"
        "try:\n"
        "    print(urllib.request.urlopen(req, timeout=30).read().decode())\n"
        "except urllib.error.HTTPError as exc:\n"
        "    print('ERR', exc.code, exc.read().decode()[:600])\n"
        "PY",
    )
    client.close()


if __name__ == "__main__":
    main()
