# Gaussian Splatting Studio

Plataforma **100% zero-CLI** que transforma **vídeos ou conjuntos de imagens** em **cenas 3D Gaussian Splatting** interativas, editáveis e calibradas em **unidades reais** (m/cm/mm e ft/in). App desktop (Tauri) + UI web (React) + API local (FastAPI) + pipeline GPU (Python/WSL2).

> A fonte de verdade de alto nível — visão, arquitetura, plano faseado, stack e decisões — é o **[`tasks.md`](./tasks.md)**.

## Status atual: consolidação (Fase 0 + wiring Fase 1–5 em código)

Implementado e **verificado por testes de código** nesta máquina (sem GPU/COLMAP/Open3D/MediaPipe/Rust):

- Monorepo pnpm com `apps/web`, `apps/api`, `apps/desktop`, `packages/{units,viewer,overlays}`, `pipeline/`, `installer/`, `docs/`.
- **Provisioner** (`pipeline/provisioner`): detecções reais de ambiente (GPU NVIDIA/driver/CUDA via `nvidia-smi`, WSL2 via `wsl --status`, disco, RAM, FFmpeg, COLMAP, Python) + verificações pós-instalação leves. As **instalações automatizadas são stubs documentados** (URLs oficiais em `pipeline/provisioner/install.py`).
- **Pipeline** (código + testes unitários): ingestão vídeo/imagens, comandos SfM/treino/export, job machine retomável (`extracting→sfm→training→exporting→meshproxy→autocal`), auto-calibração por altura com fallback se pose/depth faltar, meshproxy SKIPPED sem Open3D.
- **API local** (FastAPI): Setup + jobs (upload, progresso WS, artefatos, `DELETE /jobs/{id}`), cenas, JWT Supabase (HS256) com isolamento por usuário. WS aceita `?token=` e `?access_token=`.
- **UI web**: Setup em `/setup`; auth `/login|/signup|/reset`; jobs `/jobs|/upload|/jobs/:id`; viewer/edição/calibração/overlays atrás de `AuthGuard`. Home `/` → `/jobs`.
- **`packages/units`**, **`@gs/viewer`**, **`@gs/overlays`**: unidades, schema de cena, renderer abstrato, overlays v1 (testes Vitest).
- **Shell desktop** (`apps/desktop`): scaffold **Tauri v2** (Rust não verificado nesta máquina).
- Qualidade: eslint + prettier, ruff, `.pre-commit-config.yaml` e workflow de CI.

## Estrutura de pastas

```
├── apps/
│   ├── web/        # UI (Vite + React + TS + Zustand + React Router)
│   ├── api/        # API local FastAPI (setup, jobs, cenas, auth)
│   └── desktop/    # Shell Tauri v2 (src-tauri/)
├── packages/
│   ├── units/      # Núcleo TS de unidades reais (big.js) + testes Vitest
│   ├── viewer/     # Schema de cena, SplatRenderer, edição
│   └── overlays/   # Overlays v1 (paint/wallpaper/sticker) + shaders
├── pipeline/       # Python: provisioner, ingest, sfm, train, export, jobs, autocal, meshproxy
├── installer/      # Bootstrap do instalador (stub documentado da Fase 0)
├── docs/           # Documentação viva (aponta para tasks.md)
├── readme/         # Pasta original do workspace (preservada)
└── tasks.md        # Fonte de verdade: plano faseado, arquitetura, decisões
```

## Pré-requisitos

| Ferramenta        | Versão                    | Observação                                                                   |
| ----------------- | ------------------------- | ---------------------------------------------------------------------------- |
| Node.js           | ≥ 22.12 (ou 20.19+)       | desenvolvido com Node 23                                                     |
| pnpm              | ≥ 11                      | `corepack enable` ou `npm i -g pnpm`                                         |
| Python            | ≥ 3.11 (3.13 recomendado) | para API + pipeline                                                          |
| Rust (stable)     | mais recente              | **só para buildar o app desktop** — [rustup.rs](https://rustup.rs)           |
| GPU NVIDIA + WSL2 | —                         | exigidos pelo **pipeline de treino** (Fase 1+), não para rodar a UI de Setup |

## Como rodar (dev)

### 1. Instalar dependências JS

```powershell
pnpm install
```

### 2. Preparar o ambiente Python (venv leve — sem CUDA/torch/gsplat)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ./pipeline
.\.venv\Scripts\python -m pip install -e "./apps/api[dev]"
```

### 3. Subir a API (porta 8000)

```powershell
# com a venv ativada: pnpm dev:api
.\.venv\Scripts\python -m uvicorn app.main:app --reload --app-dir apps/api --port 8000
```

### 4. Subir a UI web (porta 5173)

```powershell
pnpm dev:web
# abre em http://localhost:5173 — a UI de Setup consome a API da porta 8000
```

A URL da API pode ser alterada via `VITE_API_URL` (ver `apps/web/.env.example`).

### 5. App desktop (opcional — requer Rust)

```powershell
pnpm dev:desktop   # = tauri dev, apontando para http://localhost:5173
```

Na primeira vez: instale o Rust via [rustup](https://rustup.rs) (no Windows, o instalador pede os _Build Tools do Visual Studio C++_). Para gerar os ícones do bundle antes de `tauri build`, rode `pnpm --filter @gs/desktop tauri icon <caminho/para/icon.png>` (o scaffold entrega `bundle.icon` vazio de propósito). Supervisão do backend pelo shell, sidecar do Provisioner e auto-update chegam nas próximas fases.

## Qualidade

```powershell
pnpm build          # build web + packages (tsc + vite)
pnpm typecheck      # typecheck TS de todos os pacotes
pnpm test           # Vitest (units, viewer, overlays, web)
pnpm lint           # eslint (flat config na raiz)
pnpm format:check   # prettier

# Python (venv):
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m pytest pipeline
.\.venv\Scripts\python -m pytest apps/api
# Não rode `pytest pipeline apps/api` no mesmo processo — ambos expõem o pacote `tests`.
```

Hooks de commit: `pip install pre-commit && pre-commit install`.

## Convenções

- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/pt-br/) (`feat:`, `fix:`, `chore:`, `ci:`, `docs:`…), atômicos e descritivos, sempre locais até definirmos o remote.
- **Versionamento**: semântico, por pacote (`apps/*`, `packages/*`, `pipeline/` têm versões próprias).
- **`tasks.md`** é a fonte de verdade de alto nível: atualizado a cada fase concluída.
- Código/identificadores em inglês; copy de UI e mensagens ao usuário em pt-BR.
