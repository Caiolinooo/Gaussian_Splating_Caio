"""List remote jobs and leftover splat data. No secrets printed."""

from __future__ import annotations

import os

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"


def run(client: paramiko.SSHClient, command: str, timeout: int = 90) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    print("CMD", command[:180])
    print(text[-8000:])
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
        "import json, urllib.request\n"
        "from pathlib import Path\n"
        "env={}\n"
        "for line in open('/home/caio/gaussian-splating/eval.env', encoding='utf-8'):\n"
        "    line=line.strip()\n"
        "    if not line or line.startswith('#') or '=' not in line: continue\n"
        "    k,v=line.split('=',1); env[k]=v\n"
        "req=urllib.request.Request('http://127.0.0.1:2222/auth/login', data=json.dumps({'username':env.get('LOCAL_AUTH_USER','caio'),'password':env.get('LOCAL_AUTH_PASSWORD','')}).encode(), headers={'Content-Type':'application/json'})\n"
        "token=json.loads(urllib.request.urlopen(req, timeout=20).read())['access_token']\n"
        "jobs=json.loads(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:2222/jobs', headers={'Authorization': f'Bearer {token}'}), timeout=20).read())\n"
        "print('JOBS', len(jobs) if isinstance(jobs,list) else jobs)\n"
        "if isinstance(jobs, list):\n"
        "    for j in jobs:\n"
        "        print(j.get('id'), j.get('state'), j.get('source',{}).get('kind'), j.get('createdAt') or j.get('created_at'))\n"
        "    Path('/tmp/gs_jobs.json').write_text(json.dumps(jobs)[:20000], encoding='utf-8')\n"
        "PY",
    )
    run(
        client,
        "cd /home/caio/gaussian-splating && "
        "echo '---DATA---'; find data jobs storage var /home/caio/gaussian-splating -maxdepth 3 -type d -iname '*cf9a69b1*' 2>/dev/null; "
        "echo '---JOB ROOTS---'; ls -la data 2>/dev/null | head; ls -la var 2>/dev/null | head; "
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "roots=[Path('/home/caio/gaussian-splating'), Path('/home/caio/gaussian-splating/var'), Path('/home/caio/gaussian-splating/data')]\n"
        "for root in roots:\n"
        "    if not root.exists():\n"
        "        continue\n"
        "    print('ROOT', root)\n"
        "    for p in sorted(root.rglob('job.json'))[:40]:\n"
        "        print(' ', p)\n"
        "    for p in sorted(root.glob('*'))[:40]:\n"
        "        print('  entry', p, 'dir' if p.is_dir() else 'file')\n"
        "PY",
    )
    run(
        client,
        "grep -n SERVE_WEB_DIR /home/caio/gaussian-splating/eval.env; "
        "ls -la /home/caio/gaussian-splating/apps/web/dist/assets | tail; "
        "python3 - <<'PY'\n"
        "import json,urllib.request\n"
        "raw=urllib.request.urlopen('http://127.0.0.1:2222/openapi.json', timeout=20).read()\n"
        "spec=json.loads(raw)\n"
        "paths=[p for p in spec.get('paths',{}) if 'rebuild' in p or 'jobs' in p]\n"
        "print('PATHS', paths)\n"
        "PY",
    )
    client.close()


if __name__ == "__main__":
    main()
