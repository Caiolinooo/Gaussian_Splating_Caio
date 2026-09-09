"""Inspect COLMAP sparse models and live job stage. Password via GS_SSH_PASS."""

from __future__ import annotations

import os
import sys

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
        f"ROOT=/home/caio/gaussian-splating/data/caio/{JOB}; "
        "echo SPARSE; ls -la $ROOT/colmap/sparse; "
        "for d in $ROOT/colmap/sparse/*; do "
        "  if [ -f $d/images.txt ]; then "
        "    imgs=$(grep -v '^#' $d/images.txt | awk 'NF>8' | wc -l); "
        "    pts=$(grep -v '^#' $d/points3D.txt 2>/dev/null | awk 'NF>7' | wc -l); "
        "    echo MODEL $d images=$imgs points=$pts; "
        "  fi; "
        "done; "
        "echo TRAIN_TAIL; tail -n 15 $ROOT/logs/train.log; "
        "python3 -c \""
        "import json,urllib.request;"
        "env={};"
        "[env.__setitem__(*line.strip().split('=',1)) for line in open('/home/caio/gaussian-splating/eval.env') if line.strip() and not line.startswith('#') and '=' in line];"
        "req=urllib.request.Request('http://127.0.0.1:2222/auth/login',data=json.dumps({'username':env.get('LOCAL_AUTH_USER','caio'),'password':env.get('LOCAL_AUTH_PASSWORD','')}).encode(),headers={'Content-Type':'application/json'});"
        "tok=json.loads(urllib.request.urlopen(req,timeout=20).read())['access_token'];"
        f"d=json.loads(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:2222/jobs/{JOB}',headers={{'Authorization':'Bearer '+tok}}),timeout=20).read());"
        "print('STATE',d.get('state'),d.get('overall_progress'));"
        "[print(s.get('name'),s.get('status'),s.get('progress'),(s.get('metrics') or {{}}).get('registered'),(s.get('metrics') or {{}}).get('matcher'),(s.get('metrics') or {{}}).get('psnr_val')) for s in (d.get('stages') or [])]"
        "\""
    )
    _stdin, stdout, stderr = client.exec_command(cmd, timeout=60, get_pty=True)
    text = stdout.read().decode("utf-8", "replace") + stderr.read().decode("utf-8", "replace")
    sys.stdout.buffer.write(text.encode("utf-8", "replace"))
    client.close()


if __name__ == "__main__":
    main()
