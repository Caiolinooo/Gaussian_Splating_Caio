# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e o projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Adicionado

- **Navegação em primeira pessoa (C2 do plano do editor)**: nova ferramenta **"Voar"** no
  viewer. WASD/setas movem a câmera pela cena, Q/E (ou PageUp/PageDown) sobem/descem,
  Shift acelera (×5), Ctrl desacelera (×1/5), CapsLock acelera (×10); o arraste gira a
  vista, a roda avança/recua e o **duplo-clique foca** o ponto da cena sob o cursor
  (funciona também na órbita). A velocidade é derivada do tamanho da cena (diagonal do
  splat: atravessar leva ~7s sem Shift), então andar dentro do ambiente tem a escala
  da captura. Implementação: `FlyControls` — wrapper fino sobre o `SparkControls`
  (`FpsMovement` + `PointerControls`) do Spark 2.1 — e `flyMath` (velocidades, limite
  de pitch, pivô à frente) em `@gs/viewer/navigation`, com testes. Ao sair do voo o
  pitch é limitado a ±85°, o roll zerado e o pivô da órbita realinhado à frente da
  câmera, sem salto. A roda do `PointerControls` acumula mesmo desabilitada — o
  wrapper zera acumulados ao ligar/desligar para não dar salto de dolly.
- Sincronização do trabalho do L4 (commit `5a3178e`): cleanup de agulhas/floaters no
  `.ply` mestre (`export/cleanup.py`), câmeras temporal no frame do ply com
  `up`/`fovY` + botão "Captura" (pose da 1ª câmera COLMAP), LOD do Spark desligado
  (merge de gaussianas-agulha em elipsoide gigante) e `Cache-Control: no-store` nos
  artefatos de splat/cena.

## [0.3.0] - 2026-09-09

Editor de splats: correção real do smearing (C0) + ferramentas de seleção e
limpeza de floaters (C1). Sincronização do trabalho desenvolvido no servidor GPU.

### Adicionado

- **Anti-smearing (C0)**: `SplatQuality` ganha 9 knobs de rasterização
  (`blurAmount`, `preBlurAmount`, `focalAdjustment`, `maxStdDev`, `clipXY`,
  `falloff`, `sortRadial`, `minPixelRadius`, `minSortIntervalMs`), com defaults
  nítidos: `blurAmount: 0`, `focalAdjustment: 2` (como o PlayCanvas/SuperSplat) e
  `maxStdDev: √5`. `SparkBackend.applyRenderKnobs()` repassa tudo ao SparkRenderer
  a cada `setQuality`. Faixas de segurança em `SPLAT_QUALITY_RANGE` +
  `clampQualityNumber`. UI em `SharpnessControls` (sliders + "Padrão nítido").
- **Seleção de splats (C1)**: módulo puro `selection/` — `projectCenter` (screen
  space), `pointInRect`/`pointInPolygon` (ray casting)/`pointInSphere`/`pointInBox`,
  `composeSelection` (replace/add/subtract/intersect) e `SelectionManager` com
  busca binária e AABB da seleção.
- **Edição de splats (C1)**: `SplatEditor` com delete, ajuste de aparência
  (brilho/saturação/temperatura/opacidade), recorte por região e recentralização.
  `decimate.ts` faz merge de gaussianas similares via grid espacial (testes de
  escala, cor e distância; combinação de variâncias; união probabilística de
  opacidade). Seis novos `EditorOp` de splat com undo/redo no `CommandStack`.
- **UI de edição**: `SplatSelectOverlay` (arrasto de retângulo/laço sobre o
  canvas, Esc cancela) e `SplatEditToolbar` (excluir, limpar, desfazer, decimar),
  ligados por `SplatSelectionContext`.
- **Métodos opcionais no contrato `SplatRenderer`**: `selectByRect`,
  `selectByLasso`, `selectByRegion`, `deleteSplats`, `adjustAppearance`,
  `cropToRegion`, `decimateSplats`, `getSplatData` — a UI degrada quando o
  backend não implementa.
- **Sincronização do servidor GPU**: commit `b5b0df9` traz 83 arquivos (+4304)
  desenvolvidos em `vm.groupabz.com` — API de jobs, supervisor, `quality.py`,
  `colmap_depth.py`, módulos `geom`/`relight`/`temporal`, `relight` e `temporal`
  no viewer, scripts de deploy.

### Corrigido

- **`resolve_master_ply` escolhia o checkpoint errado**: ordenava os `.ply` por
  texto, então `point_cloud_6999.ply` vinha depois de `point_cloud_29999.ply`
  ("6" > "2") e o meshproxy usava um checkpoint antigo. Agora ordena pelo número
  do step (`step_sort_key`).
- **SfM não tentava matcher sequencial em ratio fraco**: em vídeo com pouca
  paralaxe, o gate aprovava por `min_registered_count` mas o ratio ficava baixo
  (ex.: 10/40) e o pipeline seguia com um modelo pobre. Novo degrau tenta
  `sequential_matcher` quando o ratio está abaixo do alvo e há poses suficientes
  — sem gastar tentativa extra em material inutilizável (reprovado por count).
- `ruff` limpo: removidos imports sem uso e variáveis mortas, imports ordenados,
  linhas longas quebradas.

### Documentação

- `docs/plan-editorsplat.md`: auditoria do Spark 2.1, causa raiz do smearing e
  plano revisado em 6 componentes (corta o renderer WebGPU nativo e os parsers
  de formato, que a lib já fornece).

### Adicionado (trabalho do servidor)

- **Contrato das 4 inspirações** no SceneIO (docs): SuperSplat 3, GaussianCrowds, Video2 4DGS e paredes-sem-LiDAR + depth no forward pass — uma tabela em `docs/unified-scene-io.md`. Briefings `docs/inspiration-video24dgs.md` e `docs/inspiration-walls-depth.md`. `temporal` já cobre timesteps de vídeo; `.npz`/Comfy e `dataset/depths/` ficam reservados. `ColmapDepthProvider` documentado como stub.
- **SceneIO unificado**: um orquestrador (`detect_source_kind` → `ingest_scene` → `export_scene`) para PLY, GIF, vídeo e imagens — sem pipelines paralelos. Desenho em `docs/unified-scene-io.md`.
- **Ingestão de GIF e PLY**: GIF vira frames via ffmpeg (mesmo caminho de vídeo; mínimo de frames relaxado). PLY entra como splat pronto — SfM, treino e autocal são pulados.
- **Exportação de cena interoperável**: além de `.ply` / `.ksplat`, o job grava `scene.json` (schema `@gs/viewer`, com `temporal` e `relight`) e `scene.zip`. Novos artefatos `GET /jobs/{id}/artifacts/scene` e `/package`.
- **Viewer**: badge Spark · WebGPU quando o adapter existe; scrubber temporal e toggle de relight (contrato — sem treino 4DGS). Download do JSON/pacote na barra da cena e no job concluído.
- **Registro técnico do COLMAP por job**: stdout/stderr de cada comando é gravado em `colmap/colmap.log` (mesmo em falha) e baixável em `GET /jobs/{id}/artifacts/log`; a tela do job ganha o botão "Baixar registro COLMAP".
- Métrica `used_gpu` e artefato `log` no estágio `sfm`.
- **Login local sem Supabase**: `LOCAL_AUTH_USER` + `LOCAL_AUTH_PASSWORD` na API habilitam `POST /auth/login` (JWT HS256 assinado com `SUPABASE_JWT_SECRET`) e `GET /auth/local` (só o nome de usuário, para pré-preencher a tela). A UI entra com usuário/senha quando não há Supabase configurado, escondendo Google/signup/reset nesse modo.
- **Base da API same-origin**: sem `VITE_API_URL`, a UI usa `window.location.origin` quando servida pela própria API (`SERVE_WEB_DIR`) — fora do dev server Vite (5173). O build funciona em qualquer host/porta sem rebuild.

### Corrigido

- **Treino usa o Python do `.venv`, não `/usr/bin/python3`**: `resolve_python_bin` / `tool_paths_from_settings` passam a preferir `.venv/bin/python` (e `TOOL_PYTHON`). O job `0284bca6` gravou o Python do sistema — symlink do venv — e o `simple_trainer` caiu em `No module named 'tyro'` (`TRAINER_FAILED` em ~8s). Retry re-resolve o interpretador e retoma no treino (SfM já feito).
- **Dataset sem `images_4`**: o gsplat Parser exige `images_{data_factor}` quando o fator > 1. O ingest só gera `images/`; o runner agora cria o symlink antes de chamar o trainer.
- **Registro do trainer**: stdout/stderr (e o `argv` com o Python usado) vão para `train/train.log` e `logs/train.log` mesmo em falha — o `TRAINER_FAILED` do job `0284bca6` não deixou stderr (`No module named 'tyro'`). A mensagem passa a citar tyro/viser ou CUDA quando o detalhe contém essas strings.
- **Setup na porta 2222**: o cliente de `/setup` apontava sempre para `http://localhost:8000` (mensagem “uvicorn na porta 8000”). Agora usa a mesma origem da página; URL bakeada de loopback é ignorada fora do Vite `:5173`. `GET /setup/status` ganhou cache de 20s e checagens em paralelo.
- **Jobs lentos no L4**: clipe curto a 30 fps extraía todos os frames (job `0284bca6`: 301→188, SfM ~11 min). Ingestão capada em ~180 frames / 1280px; mapper com no máximo 8 modelos, 25 trials e BA limitado; treino default 3500 passos (3000–4000 conforme o número de frames). `TRAIN_MAX_STEPS` explícito continua valendo.
- **SfM escolhe o maior modelo COLMAP, não o `sparse/0`**: o mapper 4.x fragmentou o clipe Teams (job `0284bca6`) em 4 reconstruções; `sparse/0` tinha 5 câmeras e 1 ponto, `sparse/3` tinha 90 câmeras e 7044 pontos. O converter/gate lia só o `0` e falhava `FEW_REGISTERED` (5/188, mínimo 70%) mesmo depois do resgate SIFT. Agora todos os `sparse/N` são convertidos, o maior vai para `sparse/0` (`multiple_models` permanece ligado — `max_num_models=1` teria ficado com as 5 câmeras). O piso duro é `min_registered_count` (20 poses) e o ratio vira aviso — em vídeo o alvo cai para 40%. Mensagem deixa de mandar “filme de novo” quando o clipe era usável.
- **Ingestão de vídeo não falha mais no mínimo rígido de 150 frames**: o alvo 150–180 continua só para extração/aviso. O gate de falha é o piso inutilizável (8 frames no vídeo, 1 no GIF). O dedup 8×8 com limiar 4.0 tratava um passeio lento como tudo-duplicata (job `0284bca6`: 301 extraídos → 183 nítidos → 19 kept). Limiar padrão 1.0, relaxo 0.5 se faltar quadro. Mensagem `TOO_FEW_FRAMES` deixa de mandar “grave de novo” quando o material só era curto demais para o gate antigo. ffmpeg não faz mais upscale de 720p para 1600.
- **SfM resiliente no servidor headless**: se `feature_extractor`/matcher falharem com GPU (sem contexto OpenGL/X ou COLMAP sem CUDA), o pipeline limpa o estado parcial e repete o grafo COLMAP uma vez com `use_gpu=0` em vez de derrubar o job. Novo env `COLMAP_USE_GPU=0` força CPU desde o início.
- **Retry de job não herda mais estado parcial**: `database.db` (+ `-wal`/`-shm`) e `sparse/` de tentativas anteriores são removidos antes de cada tentativa do SfM — o `mapper` não escreve mais em `sparse/1` enquanto o `model_converter` lê um `sparse/0` velho.
- **Setup detecta COLMAP quebrado**: `detect_colmap` marca ERRO quando `colmap -h` sai com código não-zero (ex.: `libGL`/CUDA runtime ausentes), em vez de reportar OK.
- **Compatibilidade com COLMAP 4.x**: o toggle de GPU mudou de nome (`SiftExtraction.use_gpu` → `FeatureExtraction.use_gpu`, `SiftMatching.use_gpu` → `FeatureMatching.use_gpu`) e builds 4.x abortavam com "unrecognised option". O pipeline agora sonda `colmap <cmd> -h` uma vez por job e usa os nomes que o binário instalado aceita (ou omite a flag se nenhum existir).
- **Import de PLY não cai mais no meshproxy**: SfM, treino, malha proxy e autocal são pulados — um splat pronto não precisa reconstruir proxy a partir da nuvem.
- **Export não derruba mais o job sem splat-transform**: removido o fallback para `npx` (que fazia o npm tentar executar o `.ply` como pacote e falhava com `TRANSFORM_FAILED`); sem o binário do usuário, o `.ksplat` é omitido e o `.ply` mestre segue — comportamento documentado. Erros de "pacote npm ausente" também passam a ser tratados como skip.

## [0.2.0] - 2026-09-08

Pipeline real no servidor GPU (L4 24GB): Provisioner instala ffmpeg/PyTorch/gsplat; COLMAP só é localizado (nunca compilado pelo app).

### Adicionado

- Resolução automática do COLMAP do usuário (`PATH`, `TOOL_COLMAP`, `~/colmap/build/src/colmap/exe/colmap`).
- Instalação real de FFmpeg (apt) e PyTorch+CUDA / gsplat no Linux com GPU.
- Defaults L4: `data_factor=4`, SH degree 2, 7000 steps, `sequential_matcher` em vídeo e em conjuntos >80 imagens.
- Export continua com `.ply` se `splat-transform` estiver ausente; viewer já faz fallback para `.ply`.
- Env knobs: `TRAIN_MAX_STEPS`, `TRAIN_DATA_FACTOR`, `TRAIN_SH_DEGREE`, `COLMAP_MAX_EXHAUSTIVE_IMAGES`.

### Corrigido

- Provisioner não tenta `apt`/cmake do COLMAP por cima de uma compilação local.

### Documentação

- README e `tasks.md` alinhados ao caminho feliz no servidor `:2222`.

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

[0.3.0]: https://github.com/Caiolinooo/Gaussian_Splating_Caio/releases/tag/v0.3.0
[0.2.0]: https://github.com/Caiolinooo/Gaussian_Splating_Caio/releases/tag/v0.2.0
[0.1.0]: https://github.com/Caiolinooo/Gaussian_Splating_Caio/releases/tag/v0.1.0
