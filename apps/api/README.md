# API local (FastAPI)

Orquestra o Provisioner (Fase 0) e os **jobs do pipeline** (Fase 1): upload, autenticação Supabase, progresso em WebSocket e cenas versionadas.

## Como importar o pacote `pipeline/`

A API **não** instala `jobs` via `pip` no desenvolvimento. O módulo
[`app/pipeline_bridge.py`](app/pipeline_bridge.py) coloca `PIPELINE_PATH`
(default `../../pipeline`, resolvido a partir de `apps/api`) em `sys.path`
**uma única vez** no import.

```text
apps/api/app/pipeline_bridge.py  →  sys.path.insert(0, <PIPELINE_PATH>)
depois:  from jobs import JobMachine, JobSpec, ...
```

**Deploy (recomendado):** tornar o contrato instalável e usar install editável
em vez do path hack:

```powershell
pip install -e ./pipeline
```

Hoje o `pipeline/pyproject.toml` só exporta `provisioner`. Até `jobs` (e
ingest/sfm/train/export) entrarem nesse packaging, o bridge continua sendo o
caminho suportado.

## Variáveis de ambiente

| Variável                                                                                                        | Default            | Função                                                                 |
| --------------------------------------------------------------------------------------------------------------- | ------------------ | ---------------------------------------------------------------------- |
| `DATA_ROOT`                                                                                                     | `data`             | Uploads, cenas e `pipeline-jobs.sqlite`                                |
| `SUPABASE_JWT_SECRET`                                                                                           | (vazio)            | Segredo HS256 do JWT Supabase                                          |
| `SUPABASE_URL`                                                                                                  | (vazio)            | Base para JWKS (`/auth/v1/.well-known/jwks.json`) se o token for ES256 |
| `SUPABASE_JWKS_URL`                                                                                             | (vazio)            | Override do JWKS                                                       |
| `DEV_AUTH_BYPASS`                                                                                               | `0`                | `1`/`true` → usuário fixo `dev-user` (sem token)                       |
| `PIPELINE_PATH`                                                                                                 | `../../pipeline`   | Onde está o pacote `jobs`                                              |
| `MAX_UPLOAD_MB`                                                                                                 | `2048`             | Teto de upload (vídeo ou soma das imagens)                             |
| `MAX_VIDEO_DURATION_S`                                                                                          | `1200`             | Duração máxima (só se `ffprobe` estiver disponível)                    |
| `MIN_IMAGES`                                                                                                    | `20`               | Mínimo de imagens no modo `files[]`                                    |
| `TOOL_FFMPEG` / `TOOL_FFPROBE` / `TOOL_COLMAP` / `TOOL_PYTHON` / `TOOL_SIMPLE_TRAINER` / `TOOL_SPLAT_TRANSFORM` | nomes dos binários | Preenchidos em `ToolPaths` na criação do job                           |

Auth de desenvolvimento (sem projeto Supabase):

```powershell
$env:DEV_AUTH_BYPASS = "1"
```

## Contrato HTTP (frontends)

Header em todas as rotas autenticadas: `Authorization: Bearer <jwt>`.
WebSocket também aceita `?token=<jwt>` ou `?access_token=<jwt>` (compat). `/health` e `/setup/*` continuam públicos.

Erros `401` / `403` / `404` / `409` / `422` / `503` usam:

```json
{ "detail": { "message": "… (pt-BR)", "code": "UNAUTHENTICATED" } }
```

### `POST /jobs` → **202** `{ "job_id", "state" }`

`multipart/form-data`:

| Campo                | Obrigatório | Notas                                           |
| -------------------- | ----------- | ----------------------------------------------- |
| `file`               | XOR         | Um vídeo (`mp4`/`mov`/`mkv`/`webm`/`avi`/`m4v`) |
| `files` ou `files[]` | XOR         | Imagens `jpg`/`png`/`heic` — mínimo 20          |
| `user_height_m`      | sim         | `> 0` e entre `0,5` e `2,8` m                   |
| `idempotency_key`    | sim         | Reuso do mesmo job por usuário                  |

Arquivos em `{DATA_ROOT}/{user_id}/{job_id}/uploads/`. O `JobMachine.create` roda na request; `machine.run` vai para uma task asyncio (não bloqueia).

### `GET /jobs` → `{ "jobs": [ JobSummary ] }`

`JobSummary`: `job_id`, `state`, `source_kind`, `user_height_m`, `created_at`, `updated_at`, `overall_progress`, `last_completed_stage`, `error_*`, `idempotency_key`.

### `GET /jobs/{id}` → `JobDetail`

`JobSummary` + `stages[]` (`name`, `status`, `progress`, `message`, `metrics`, …) + `work_dir`.

### `POST /jobs/{id}/cancel` → **200** `{ "job_id", "state" }`

Propaga `machine.cancel` (flag `cancel_requested`; queued vira `cancelled` na hora).

### `POST /jobs/{id}/retry` → **202** `{ "job_id", "state" }`

Só `error` ou `cancelled`. Chama `machine.retry` e dispara `run` de novo.

### `DELETE /jobs/{id}` → **204**

Remove o registro e os artefatos do usuário (pasta do job). Isolado por dono.

### `WS /jobs/{id}/events`

Primeira mensagem = snapshot atual (`ProgressEvent`). Em seguida o stream.
Fecha com `1000` em `done`/`error`/`cancelled`. Reconectar é seguro: o snapshot
volta primeiro. Códigos `4401` (sem auth), `4403` (outro usuário), `4404` (job inexistente).

```json
{
  "job_id": "…",
  "state": "training",
  "stage": "training",
  "stage_progress": 0.4,
  "overall_progress": 0.5,
  "message": "…",
  "metrics": {},
  "timestamp": "…"
}
```

### `GET /jobs/{id}/artifacts/{kind}`

`kind` ∈ `ply` | `ksplat` | `thumbnail`. Stream do arquivo sob
`{work_dir}/export/` (`master.ply`, `scene.ksplat`, `thumbnails/preview.jpg`).
Path traversal é rejeitado (enum + resolução sob `DATA_ROOT/{user_id}`).

### `GET /scenes/{id}` / `PUT /scenes/{id}`

JSON versionado por usuário (`schema_version: 1`). `PUT` com `version` diferente
da persistida → **409** `{ "code": "VERSION_CONFLICT", "current_version": N }`.
O servidor incrementa `version` após um PUT bem-sucedido.

Isolamento: o usuário A nunca lê jobs, artefatos, eventos ou cenas do usuário B.

## Supervisão do JobMachine

1. Store SQLite em `{DATA_ROOT}/pipeline-jobs.sqlite` (`SqliteJobStore` do pipeline).
2. `JobSupervisor` mantém um registry `job_id → asyncio.Task`.
3. `run` é **bloqueante** — executa em `run_in_executor`. A request HTTP não espera o pipeline.
4. `cancel` na API chama `machine.cancel`; a máquina observa `cancel_requested` entre etapas.
5. Restart da API **não apaga** jobs. No boot, estados `queued|extracting|sfm|training|exporting|autocal` são recolocados em `machine.run` (resume-safe).
6. `ProgressHub` faz fan-out thread-safe do `ProgressSink` do pipeline para os WebSockets.

Em testes o `JobMachine` é um fake in-memory (`tests/fakes.py`).

## Como rodar

```powershell
# venv da raiz do monorepo
.\.venv\Scripts\python -m uvicorn app.main:app --reload --app-dir apps/api --port 8000
```

```powershell
.\.venv\Scripts\python -m pytest apps/api/tests -q
.\.venv\Scripts\python -m ruff check apps/api
```

## Pendências de deploy

- **Editable install** do pipeline com o pacote `jobs` declarado (hoje só `provisioner`).
- **Supabase real**: `SUPABASE_JWT_SECRET` (HS256) ou JWKS/ES256 com PyJWT+cryptography; `DEV_AUTH_BYPASS=0`.
- **WSL2 + CUDA**: `machine.run` chama ffmpeg/COLMAP/gsplat — no Windows nativo isso é frágil; o worker de treino deve viver no WSL2/servidor GPU.
- `python-multipart` já está nas dependências da API (upload). `pydantic-settings` é opcional (há fallback via env).
