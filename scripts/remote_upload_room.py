"""Upload room renderer and submit the quality job."""

from __future__ import annotations

import os
from pathlib import Path

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"
ROOT = Path(__file__).resolve().parents[1]


def run(client: paramiko.SSHClient, command: str, timeout: int = 300) -> str:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    print("CMD", command[:160])
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
    sftp = client.open_sftp()
    try:
        sftp.mkdir("/home/caio/gaussian-splating/scripts")
    except OSError:
        pass
    sftp.put(str(ROOT / "scripts/make_textured_room.py"), "/home/caio/gaussian-splating/scripts/make_textured_room.py")
    sftp.close()
    run(
        client,
        "cd /home/caio/gaussian-splating && .venv/bin/python scripts/make_textured_room.py /tmp/gs-room && ls /tmp/gs-room | wc -l",
        timeout=240,
    )
    run(
        client,
        "python3 - <<'PY'\n"
        "import json, urllib.error, urllib.request\n"
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
        "print('frames', len(frames))\n"
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
        "try:\n"
        "    print(urllib.request.urlopen(req, timeout=180).read().decode())\n"
        "except urllib.error.HTTPError as exc:\n"
        "    print('ERR', exc.code, exc.read().decode()[:800])\n"
        "PY",
        timeout=240,
    )
    client.close()


if __name__ == "__main__":
    main()
