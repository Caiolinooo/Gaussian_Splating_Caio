"""Wait until job is idle, then rebuild from training on promoted sparse."""

from __future__ import annotations

import os
import sys

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"
JOB = "3ce6fee7-a665-450d-990f-2284331fe5e6"


def run(client: paramiko.SSHClient, command: str, timeout: int = 180) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    sys.stdout.buffer.write(text.encode("utf-8", "replace"))
    return text


def main() -> None:
    password = os.environ.get("GS_SSH_PASS")
    if not password:
        raise SystemExit("GS_SSH_PASS ausente")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=30, look_for_keys=False, allow_agent=False)
    run(
        client,
        "python3 - <<'PY'\n"
        "import json, time, urllib.request\n"
        f"job='{JOB}'\n"
        "env={}\n"
        "for line in open('/home/caio/gaussian-splating/eval.env', encoding='utf-8'):\n"
        "    line=line.strip()\n"
        "    if not line or line.startswith('#') or '=' not in line: continue\n"
        "    k,v=line.split('=',1); env[k]=v\n"
        "def token():\n"
        "    req=urllib.request.Request('http://127.0.0.1:2222/auth/login', data=json.dumps({'username':env.get('LOCAL_AUTH_USER','caio'),'password':env.get('LOCAL_AUTH_PASSWORD','')}).encode(), headers={'Content-Type':'application/json'})\n"
        "    return json.loads(urllib.request.urlopen(req, timeout=20).read())['access_token']\n"
        "tok=token()\n"
        "for _ in range(40):\n"
        "    d=json.loads(urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:2222/jobs/{job}', headers={'Authorization': f'Bearer {tok}'}), timeout=20).read())\n"
        "    print('wait', d.get('state'), d.get('overall_progress'))\n"
        "    if d.get('state') in {'done','error','cancelled'}:\n"
        "        break\n"
        "    time.sleep(8)\n"
        "tok=token()\n"
        "req=urllib.request.Request(f'http://127.0.0.1:2222/jobs/{job}/rebuild?from_stage=training', method='POST', headers={'Authorization': f'Bearer {tok}'})\n"
        "print(urllib.request.urlopen(req, timeout=30).read().decode())\n"
        "PY",
        timeout=360,
    )
    client.close()


if __name__ == "__main__":
    main()
