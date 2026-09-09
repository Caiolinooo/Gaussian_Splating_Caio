"""On the L4 host: render room frames and POST /jobs. Password via GS_SSH_PASS."""

from __future__ import annotations

import os

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"


def run(client: paramiko.SSHClient, command: str, timeout: int = 300) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    print("CMD", command[:160])
    print(text[-5000:])
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
        "cd /home/caio/gaussian-splating && "
        ".venv/bin/python scripts/make_textured_room.py /tmp/gs-room && "
        "ls /tmp/gs-room | wc -l",
        timeout=180,
    )
    run(
        client,
        "python3 - <<'PY'\n"
        "import json, mimetypes, urllib.request\n"
        "from pathlib import Path\n"
        "from uuid import uuid4\n"
        "env={}\n"
        "for line in open('/home/caio/gaussian-splating/eval.env', encoding='utf-8'):\n"
        "    line=line.strip()\n"
        "    if not line or line.startswith('#') or '=' not in line: continue\n"
        "    k,v=line.split('=',1); env[k]=v\n"
        "req=urllib.request.Request('http://127.0.0.1:2222/auth/login', data=json.dumps({'username':env.get('LOCAL_AUTH_USER','caio'),'password':env.get('LOCAL_AUTH_PASSWORD','')}).encode(), headers={'Content-Type':'application/json'})\n"
        "token=json.loads(urllib.request.urlopen(req, timeout=20).read())['access_token']\n"
        "frames=sorted(Path('/tmp/gs-room').glob('*.jpg'))\n"
        "boundary='----gsroom'+uuid4().hex\n"
        "chunks=[]\n"
        "def add(name, value, filename=None, ctype=None):\n"
        "    part=[f'--{boundary}','Content-Disposition: form-data; name=\"%s\"' % name]\n"
        "    if filename:\n"
        "        part[1]+=f'; filename=\"{filename}\"'\n"
        "        part.append(f'Content-Type: {ctype or \"image/jpeg\"}')\n"
        "    part.append('')\n"
        "    if isinstance(value, bytes):\n"
        "        chunks.append(('\\r\\n'.join(part)+'\\r\\n').encode()+value+b'\\r\\n')\n"
        "    else:\n"
        "        chunks.append(('\\r\\n'.join(part)+'\\r\\n'+value+'\\r\\n').encode())\n"
        "add('user_height_m','1.75')\n"
        "add('idempotency_key','room-quality-'+uuid4().hex[:8])\n"
        "for path in frames:\n"
        "    add('files[]', path.read_bytes(), path.name, 'image/jpeg')\n"
        "body=b''.join(chunks)+f'--{boundary}--\\r\\n'.encode()\n"
        "req=urllib.request.Request('http://127.0.0.1:2222/jobs', data=body, method='POST', headers={'Authorization': f'Bearer {token}','Content-Type': f'multipart/form-data; boundary={boundary}'})\n"
        "print(urllib.request.urlopen(req, timeout=120).read().decode())\n"
        "PY",
        timeout=180,
    )
    client.close()


if __name__ == "__main__":
    main()
