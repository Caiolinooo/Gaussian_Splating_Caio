"""Print remote job list/detail. Password via GS_SSH_PASS only."""

from __future__ import annotations

import os

import paramiko

HOST = "vm.groupabz.com"
USER = "caio"


def main() -> None:
    password = os.environ.get("GS_SSH_PASS")
    if not password:
        raise SystemExit("GS_SSH_PASS ausente")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=password, timeout=30, look_for_keys=False, allow_agent=False)
    _stdin, stdout, stderr = client.exec_command(
        "python3 - <<'PY'\n"
        "import json, urllib.request\n"
        "env={}\n"
        "for line in open('/home/caio/gaussian-splating/eval.env', encoding='utf-8'):\n"
        "    line=line.strip()\n"
        "    if not line or line.startswith('#') or '=' not in line: continue\n"
        "    k,v=line.split('=',1); env[k]=v\n"
        "req=urllib.request.Request('http://127.0.0.1:2222/auth/login', data=json.dumps({'username':env.get('LOCAL_AUTH_USER','caio'),'password':env.get('LOCAL_AUTH_PASSWORD','')}).encode(), headers={'Content-Type':'application/json'})\n"
        "token=json.loads(urllib.request.urlopen(req, timeout=20).read())['access_token']\n"
        "jobs=json.loads(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:2222/jobs', headers={'Authorization': f'Bearer {token}'}), timeout=20).read())\n"
        "items=jobs.get('jobs') if isinstance(jobs, dict) else jobs\n"
        "print('JOBS', json.dumps([{k:j.get(k) for k in ('job_id','state','overall_progress','error_message')} for j in (items or [])], indent=2))\n"
        "if items:\n"
        "    jid=items[-1]['job_id']\n"
        "    detail=json.loads(urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:2222/jobs/{jid}', headers={'Authorization': f'Bearer {token}'}), timeout=20).read())\n"
        "    print('STATE', detail.get('state'), 'progress', detail.get('overall_progress'))\n"
        "    stages=detail.get('stages') or []\n"
        "    for st in stages:\n"
        "        m=st.get('metrics') or {}\n"
        "        print(st.get('name'), st.get('status'), st.get('progress'), st.get('message'), {k:m.get(k) for k in ('registered','input_images','ratio','matcher','psnr_val','num_gaussians','temporal_cameras','relight','wall_planes') if k in m})\n"
        "PY",
        timeout=60,
        get_pty=True,
    )
    print(stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace"))
    client.close()


if __name__ == "__main__":
    main()
