# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e o projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [0.1.0] - 2026-09-08

Primeira entrega usável do monorepo (UI + API + contratos de pipeline). **Não** inclui CUDA, COLMAP, gsplat nem treino GPU.

### Adicionado

- Shell persistente (`AppShell`) com navegação Setup / Jobs / Upload / Viewer / Edição / Calibração / Overlays.
- Título do documento (`<title>`) por rota.
- Timeline de job via `applyEvent` (etapas anteriores concluídas, ETA zerado em estado terminal).
- Canal SSE `GET /jobs/{id}/events` como fallback do WebSocket.
- UI e persistência de overlays em pt-BR, com testes.
- Avaliação em um único entry HTTP: `SERVE_WEB_DIR` serve `apps/web/dist` na mesma porta da API (ex.: `2222`).
- `CORS_ORIGINS` (CSV, JSON ou `*`) para preview remoto.

### Corrigido

- Job terminal não volta a “Reconectando…”.
- COLMAP ausente vira `COLMAP_FAILED` com mensagem acionável (Setup), sem disparar treino.
- Viewer sem artefato mostra progresso/CTA em vez de tela vazia.
- `dev@localhost` aceito só com bypass de desenvolvimento.

### Documentação

- README com como rodar web (`5173`), API (`8000`) e avaliação porta `2222`.
- `tasks.md` atualizado com a auditoria de UI/workflow.

[0.1.0]: https://github.com/Caiolinooo/Gaussian_Splating_Caio/releases/tag/v0.1.0
