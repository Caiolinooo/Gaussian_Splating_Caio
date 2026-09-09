# Gaussian Splatting Studio

Versão **0.3.0** — changelog em [`CHANGELOG.md`](./CHANGELOG.md).

Plataforma **100% zero-CLI** que transforma **vídeos ou conjuntos de imagens** em **cenas 3D Gaussian Splatting** interativas, editáveis e calibradas em **unidades reais** (m/cm/mm e ft/in). App desktop (Tauri) + UI web (React) + API local (FastAPI) + pipeline GPU (Python/WSL2).

> A fonte de verdade de alto nível — visão, arquitetura, plano faseado, stack e decisões — é o **[`tasks.md`](./tasks.md)**.

## Status atual: 0.3.0 — editor de splats (anti-smearing + limpeza de floaters)

App de avaliação: **http://vm.groupabz.com:2222** (UI+API, login local). WebGPU: **https://vm.groupabz.com:2223** (mesmo app, TLS).

- Monorepo pnpm com `apps/web`, `apps/api`, `apps/desktop`, `packages/{units,viewer,overlays}`, `pipeline/`, `installer/`, `docs/`.
- **Provisioner** (`pipeline/provisioner`): detecção real + instalação de FFmpeg/PyTorch+CUDA/gsplat no Linux com GPU. **COLMAP não é compilado nem instalado via apt** — o app localiza o binário do usuário (`which colmap` ou `~/colmap/build/src/colmap/exe/colmap`).
- **Defaults L4 24GB / 50GB RAM**: ingestão 150–180 frames (1280px), `sequential_matcher` em vídeo (e em >80 imagens), mapper com 1 modelo, treino `data_factor=4`, SH 2, **3500 steps** (~15–25 min no caminho rápido). `TRAIN_MAX_STEPS` sobe a qualidade.
- **Pipeline** (código + testes unitários): ingestão vídeo/imagens, comandos SfM/treino/export, job machine retomável (`extracting→sfm→training→exporting→meshproxy→autocal`), auto-calibração por altura com fallback se pose/depth faltar, meshproxy SKIPPED sem Open3D.
- **API local** (FastAPI): Setup + jobs (upload, progresso WS, artefatos, `DELETE /jobs/{id}`), cenas, JWT Supabase (HS256) com isolamento por usuário. WS aceita `?token=` e `?access_token=`.
- **UI web**: Setup em `/setup`; auth `/login|/signup|/reset`; jobs `/jobs|/upload|/jobs/:id`; viewer/edição/calibração/overlays atrás de `AuthGuard`. Home `/` → `/jobs`.
- **`packages/units`**, **`@gs/viewer`**, **`@gs/overlays`**: unidades, schema de cena, renderer abstrato, overlays v1 (testes Vitest).
- **Shell desktop** (`apps/desktop`): scaffold **Tauri v2** (Rust não verificado nesta máquina).
- Qualidade: eslint + prettier, ruff, `.pre-commit-config.yaml` e workflow de CI.

## Editor de splats (0.3.0)

### Anti-smearing: a causa real

O plano original previa um renderer WebGPU nativo com radix sort em WGSL. A
auditoria do Spark 2.1 mostrou que **ele já faz sort por frame na GPU**
(`readbackDepth` → `sortSplats32` em worker WASM). O smearing vinha de três
knobs com defaults ruins:

| Knob | Default do Spark | Correção | Efeito |
| ---- | ---------------- | -------- | ------ |
| `blurAmount` | `0.3` | **`0.0`** | Soma ~0,5px na covariância 2D — infla cada gaussiana |
| `focalAdjustment` | `1.0` | **`2.0`** | 2.0 reproduz o PlayCanvas/SuperSplat |
| `maxStdDev` | `√8 ≈ 2.83` | **`√5 ≈ 2.24`** | Caudas longas = streaks |

Todas expostas em `SharpnessControls` (botão **Nitidez** no HUD), com
**Padrão nítido** para voltar aos valores acima.

> Detalhes e o plano completo: [`docs/plan-editorsplat.md`](./docs/plan-editorsplat.md).

### Ferramentas de edição

| Ferramenta | Como usar | Observação |
| ---------- | --------- | ---------- |
| **Retângulo** | arraste no canvas | seleção em screen space (projeta os centros) |
| **Laço** | desenhe no canvas | point-in-polygon por ray casting |
| **Excluir seleção** | após selecionar | remove floaters |
| **Decimar** | informe o alvo | merge de gaussianas similares (grid espacial) |
| **Desfazer** | — | histórico próprio de buffers |

`Esc` cancela a ferramenta ativa. A seleção suporta os modos `replace`, `add`,
`subtract` e `intersect`.

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
# abre em http://localhost:5173 — o Vite faz proxy da API para
# http://vm.groupabz.com:2222 (override: GS_API_PROXY)
```

Para apontar direto a outra API, use `VITE_API_URL` (ver `apps/web/.env.example`).

Auth de desenvolvimento (sem Supabase): `DEV_AUTH_BYPASS=1` na API e `VITE_DEV_AUTH_BYPASS=1` na web.

### 5. Avaliação em um único entry (porta 2222)

Sobe **só UI + API** (sem CUDA, COLMAP, gsplat ou treino GPU). A FastAPI serve o build Vite quando `SERVE_WEB_DIR` aponta para `apps/web/dist`.

```powershell
pnpm install
pnpm --filter @gs/web build
# no build, defina a URL pública da API (mesmo host/porta se for entry único):
# $env:VITE_API_URL = "http://SEU-HOST:2222"
# $env:VITE_DEV_AUTH_BYPASS = "1"

$env:DEV_AUTH_BYPASS = "1"
$env:CORS_ORIGINS = "http://localhost:2222,http://SEU-HOST:2222"
$env:SERVE_WEB_DIR = (Resolve-Path .\apps\web\dist).Path
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 2222
```

Linux (avaliação remota):

```bash
export VITE_API_URL="http://vm.groupabz.com:2222"
export VITE_DEV_AUTH_BYPASS=1
pnpm --filter @gs/web build

export DEV_AUTH_BYPASS=1
export CORS_ORIGINS="http://vm.groupabz.com:2222,http://localhost:2222"
export SERVE_WEB_DIR="$PWD/apps/web/dist"
.venv/bin/python -m uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 2222
```

A UI fica em `http://<host>:2222`. `/health` continua na mesma porta. **Não** instala toolchain de GPU neste modo.

### 6. App desktop (opcional — requer Rust)

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

- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/pt-br/) (`feat:`, `fix:`, `chore:`, `ci:`, `docs:`…).
- **Versionamento**: semântico (`0.1.0` no monorepo; `apps/*`, `packages/*`, `pipeline/` acompanham). Remote: `https://github.com/Caiolinooo/Gaussian_Splating_Caio` (`main`).
- **`tasks.md`** é a fonte de verdade de alto nível: atualizado a cada fase concluída.
- Código/identificadores em inglês; copy de UI e mensagens ao usuário em pt-BR.
