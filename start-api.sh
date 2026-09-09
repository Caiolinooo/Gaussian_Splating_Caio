#!/usr/bin/env bash
cd /home/caio/gaussian-splating
set -a; source eval.env; set +a
exec .venv/bin/python -m uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 2222 >> eval-2222.log 2>&1
