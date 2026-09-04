# Tasks — Plataforma de Gaussian Splatting a partir de Vídeo

> Plano de ação de alto nível. Documento vivo: atualizar a cada fase concluída.
> Última revisão: 2026-09-04 (3ª revisão — **Fase 0 executada**: monorepo consolidado na raiz, Provisioner com detecções reais + API FastAPI + UI de Setup verificados de verdade, núcleo de unidades testado, shell Tauri v2 scaffoldado, qualidade/CI configurados; instalações automatizadas do Provisioner seguem como stubs documentados — ver checklist da Fase 0 em §5).
> Revisão anterior: 2026-09-04 (2ª revisão — incorpora: pipeline zero-CLI com setup automatizado, entrada mínima de dados [vídeo/imagens + altura], auto-calibração por altura e ferramenta de medida em tempo real no viewer; e consolida as 5 decisões tomadas em 2026-09-04 — ver §7).

---

## 1. Visão geral e objetivo do produto

Aplicação end-to-end, **100% zero-CLI**, que transforma **vídeos ou conjuntos de imagens** em **cenas 3D Gaussian Splatting interativas, editáveis e calibradas em unidades reais**:

1. **Geração automatizada**: vídeo (ou upload múltiplo de imagens) → extração de frames → SfM (COLMAP) → treino 3DGS → splat (.ply master + .ksplat web). Todo o workflow — incluindo **preparação do ambiente, download e instalação de dependências (ffmpeg, COLMAP, Python/CUDA, gsplat)** — é executado e acompanhado por **UI própria**: o usuário final **nunca executa comandos manualmente**. Evolução futura para cenas dinâmicas/movimentos complexos (inspirado em MoE-GS — mixture-of-experts para dynamic Gaussian splatting, IEEE TPAMI Set/2026).
2. **Entrada mínima de dados**: o usuário fornece apenas (a) vídeo **ou** conjunto de imagens e (b) **sua altura**. A altura alimenta a **auto-calibração de escala** (detecção de pessoa/pose nos frames estima a altura na cena e cruza com a altura real informada).
3. **Visualização**: viewer web interativo (orbit, pan, zoom, seleção por clique).
4. **Edição**: inserção de objetos 3D (GLB/glTF e/ou splats adicionais) com manipulação via gizmos (translação, rotação, escala) — **sempre já em unidades reais calibradas**.
5. **Unidades reais em tempo real**: ferramenta trena/régua ponto-a-ponto **live dentro do viewer**, disponível a qualquer momento (antes e durante a inserção de objetos/imagens) — não é um passo separado de setup. Dimensões exatas em metros/cm/mm **e** pés/polegadas, com conversão entre sistemas.
6. **Overlays de textura**: sobrepor imagens/texturas sobre superfícies (novas cores, papéis de parede, adesivos) via decals projetivos sobre proxy geométrico — **com escala em unidades reais**.

---

## 2. Estado atual do projeto (levantamento em 2026-09-04)

- Workspace: `D:\Projeto\Desenvolvendo\Gaussian_Splating_Caio`.
- **Projeto greenfield**: o workspace contém apenas a pasta `readme/` com um repositório git recém-inicializado (branch `master`, **sem commits, sem remote, sem arquivos**).
- Não existe código, README, `package.json`, `pyproject.toml`, `requirements.txt`, viewer, scripts de treino ou pipeline.
- **Conclusão**: o plano começa do zero (Fase 0 = fundação + instalador automatizado). Nada a estender; tudo a construir.
- **Decisões de produto/arquitetura tomadas em 2026-09-04** estão consolidadas em §7 e já refletidas nas fases e na stack.
- **Atualização (2026-09-04, 3ª revisão)**: Fase 0 executada — o workspace agora tem o monorepo funcional (ver `README.md` e o checklist da Fase 0 em §5).

---

## 3. Arquitetura proposta

Visão em camadas, com separação clara entre **pipeline offline (Python/GPU)** e **aplicação web (TypeScript)**, e com **automação de ambiente** como componente de primeira classe:

```
┌──────────────────────────────────────────────────────────────────────────┐
│ FRONTEND (React + Vite + TS)                                             │
│  ├─ UI Shell (upload vídeo/imagens + altura, jobs, painéis, conta)       │
│  ├─ UI de Setup (progresso do Provisioner: etapas, %, saúde do ambiente) │
│  ├─ UI de Pipeline em tempo real (WebSocket/SSE: etapas, logs, %)        │
│  ├─ Viewer 3D (three.js + interface SplatRenderer → Spark | @mkkellogg)  │
│  ├─ Camada de Edição (gizmos, hierarquia de cena, undo/redo)             │
│  ├─ Camada de Unidades (trena live, auto-calibração, SI↔imperial)        │
│  └─ Camada de Texturas (decals projetivos sobre proxy de malha)          │
├──────────────────────────────────────────────────────────────────────────┤
│ BACKEND (FastAPI + fila de jobs + Supabase Auth)                         │
│  ├─ API REST: upload, status de job, artefatos, cenas salvas             │
│  ├─ Canal tempo real (WebSocket/SSE): progresso de setup e de pipeline   │
│  ├─ Bootstrap/Provisioner: detecta GPU/CUDA, baixa e instala ffmpeg,     │
│  │   COLMAP, env Python, gsplat; verifica saúde; reporta à UI            │
│  ├─ Serviço de Auto-calibração: detecção de pessoa/pose nos frames →     │
│  │   estimativa de escala pela altura informada (fallback: manual)       │
│  └─ Storage de artefatos (vídeos, imagens, frames, COLMAP, .ply/.ksplat) │
├──────────────────────────────────────────────────────────────────────────┤
│ PIPELINE GPU (Python, servidor GPU próprio; dev em WSL2 + CUDA)          │
│  vídeo/imagens → ffmpeg (frames, se vídeo) → COLMAP (SfM) → gsplat       │
│  (treino) → export .ply (master) → compressão .ksplat (web)              │
│  + Auto-calibração por altura (pós-SfM/treino)                           │
│  Fase futura: malha proxy (2DGS/SuGaR) + dynamic GS (MoE-GS)             │
└──────────────────────────────────────────────────────────────────────────┘
```

Decisões estruturais:
- **Zero-CLI**: toda operação (setup, ingestão, treino, export) é disparada e acompanhada pela UI; CLIs existem apenas encapsulados no Provisioner/pipeline, nunca expostos ao usuário final.
- **Distribuição desktop via Tauri** (decisão 2026-09-04): janela nativa leve que encapsula UI web + backend local + Provisioner (sidecar), com auto-update — o usuário final só instala e abre.
- **Monorepo** (ex.: `apps/web`, `apps/api`, `packages/units`, `pipeline/`, `installer/`): o núcleo de unidades é compartilhado e testável isoladamente.
- **Pipeline assíncrono baseado em jobs, idempotente e retomável**: treino 3DGS leva minutos→horas; cada etapa persiste estado e permite resume. O Provisioner valida o ambiente **antes** de qualquer job iniciar.
- **Progresso em tempo real**: WebSocket/SSE publica etapa atual, % e logs tanto do setup quanto do pipeline.
- **Renderer desacoplado**: interface `SplatRenderer` própria abstrai o motor de splats — **Spark (primário, WebGPU)** com **fallback automático para @mkkellogg/gaussian-splats-3d** (WebGL2) quando WebGPU indisponível (decisão 2026-09-04).
- **Separação splat × objetos**: o splat reconstruído é o "cenário"; objetos GLB/splats adicionais vivem como nós independentes na cena three.js.
- **Calibração como capacidade live do viewer**, não etapa de setup: o fator de escala (auto ou manual) aplica-se a um nó-raiz da cena e pode ser redefinido a qualquer momento; todos os consumidores (objetos, overlays, trena) leem as unidades desse nó.
- **Formato de cena próprio** (JSON): referencia splat de fundo + objetos + transformações + calibração (fator, origem: auto-altura/manual, confiança) + overlays. Viewer reconstrói tudo a partir dele.

---

## 4. Fluxo do usuário ponta a ponta

1. **Instala** a aplicação/ambiente rodando **um único instalador** — sem comandos manuais.
2. **Setup automático**: o Provisioner detecta GPU/CUDA, baixa e instala ffmpeg, COLMAP, ambiente Python e gsplat; barra de progresso por etapa na UI; ao final, **relatório de saúde do ambiente** (GPU, versões, espaço em disco) com verde/vermelho e ações guiadas de correção.
3. **Cria conta** (Supabase Auth) e entra no workspace multiusuário.
4. **Envia os dados mínimos**: um vídeo **ou** um conjunto de imagens + **sua altura** (ex.: 1,75 m). Nada mais é exigido.
5. **Acompanha o job em tempo real**: etapas `upload → extract → sfm → training → export → auto-calibração`, com % por etapa, logs acessíveis e erros explicáveis (ex.: "poucas correspondências no SfM — grave com mais textura/luz").
6. **Abre a cena** no viewer assim que o job conclui.
7. **Confirma/define a medida de referência ao vivo**: se a auto-calibração por altura encontrou fator de escala, o viewer pré-aplica e pede confirmação ("a distância entre estes pontos parece X m?"); o usuário confirma, ajusta ou redefine a qualquer momento com a **trena ponto-a-ponto**.
8. **Insere objetos 3D e imagens** (GLB, splats extras, papéis de parede, adesivos) **já com medidas reais visíveis** durante o posicionamento — m/cm/mm ou ft/in conforme preferência, com conversão instantânea.
9. **Salva e compartilha** a cena; ao reabrir, calibração, objetos e overlays são restaurados.

---

## 5. Plano faseado

### Fase 0 — Fundação, instalador automatizado e Provisioner

**Objetivo**: repositório estruturado e **setup 100% automatizado com UI de progresso** — máquina limpa → um instalador → ambiente pronto.

- [x] Inicializar monorepo na raiz (git de `readme/` consolidado na raiz, `.gitignore` completo, commits atômicos locais; **remote propositalmente adiado** — sem push nesta fase, por instrução de 2026-09-04).
- [x] Estruturar pastas: `apps/web` (Vite+React+TS), `apps/api` (FastAPI), `apps/desktop` (shell Tauri), `pipeline/` (Python), `packages/units` (TS), `installer/` (bootstrap), `docs/`.
- [ ] **Shell desktop Tauri** (decisão 2026-09-04): scaffold Tauri v2 criado em `apps/desktop` (janela nativa apontando para o dev server do `apps/web`); **pendentes**: sidecar do Provisioner, supervisão do backend local (processos filhos), gate da UI de Setup antes de liberar o app e auto-update. (Rust não instalado nesta máquina — build do shell ainda não verificado; instruções no README.)
- [ ] **Bootstrap/Provisioner**: detecções **reais** implementadas e verificadas (GPU NVIDIA/driver/CUDA via `nvidia-smi`, WSL2 via `wsl --status`, espaço em disco, memória RAM, ffmpeg, COLMAP, Python) + verificações leves pós-instalação (`ffmpeg -version`, `colmap -h`); **pendentes (stubs documentados com URLs oficiais em `pipeline/provisioner/install.py`)**: download/instalação automatizados de ffmpeg, COLMAP, env Python (PyTorch+CUDA) e gsplat via wheel pré-compilada, import test do gsplat e render smoke test.
- [x] **UI de Setup**: tela de progresso por etapa, barra de %, log expansível e relatório de saúde do ambiente com status por componente e ações guiadas de correção — implementada em `apps/web` (pt-BR) consumindo a API real (`GET /setup/status`, `POST /setup/install`, `GET /setup/progress`) com loading/erro; verificada com browser automatizado (zero erros de console/rede).
- [x] Tratamento de erro guiado no setup: mensagens acionáveis por componente (`fix_hint`), botão "tentar novamente" e download do registro de logs para suporte (pacote de logs completo chega com o instalador real).
- [ ] Pré-checagem automática antes de qualquer job do pipeline (o endpoint `GET /setup/status` já entrega o veredito `ready`; o **gate no worker** chega junto com a fila de jobs na Fase 1).
- [x] Lint/format (ruff, eslint/prettier), pre-commit, CI básico (build web + typecheck + testes do núcleo de unidades + ruff check + pytest) — `.github/workflows/ci.yml`, `.pre-commit-config.yaml`.
- [x] Definir convenções: Conventional Commits, versionamento semântico por pacote, este `tasks.md` como fonte de verdade — documentado no `README.md`.

**Tecnologias**: **Tauri** (decisão 2026-09-04) como shell desktop; pnpm workspaces ou turborepo; FastAPI; WSL2/Docker; scripts de provisionamento idempotentes (PowerShell + bash/WSL) executados pelo Provisioner via sidecar do Tauri; GitHub Actions.
**Critérios de aceite**: **máquina limpa (Windows, sem WSL2/COLMAP/ffmpeg) → executar UM instalador → ambiente pronto sem nenhum comando manual**, com relatório de saúde 100% verde na UI; instalador é idempotente (re-executar não quebra nada); falha simulada (ex.: sem GPU) gera mensagem guiada compreensível por não-técnico; CI verde.

---

### Fase 1 — Pipeline (vídeo OU imagens) → 3DGS, com auth e UI de acompanhamento

**Objetivo**: dado um vídeo **ou** um conjunto de imagens (+ altura do usuário), produzir splat `.ply` (master) + `.ksplat` (web) de qualidade, com acompanhamento em tempo real e auto-calibração candidata.

- [ ] **Contas e multiusuário desde já** (decisão 2026-09-04): **Supabase Auth** (e-mail/senha + OAuth), sessões no frontend, autorização por usuário nos endpoints, isolamento de jobs/artefatos por usuário.
- [ ] Upload via API: **vídeo (multipart) OU upload múltiplo de imagens** (jpg/png/heic); se imagens, **pular a etapa ffmpeg**; validações (formato, duração/qtd. mínima, resolução) e storage versionado por usuário/job.
- [ ] **Campo de altura do usuário** no fluxo de upload (obrigatório no MVP; persistir com o job para a auto-calibração).
- [ ] Extração de frames com **ffmpeg** (somente para vídeo): taxa adaptativa (alvo 150–400 frames), detecção de blur/dedup (laplacian variance), normalização de resolução.
- [ ] SfM com **COLMAP**: `feature_extractor` (SIFT) → `exhaustive_matcher` (ou `sequential_matcher` para vídeo contíguo) → `mapper`; falhar com mensagem clara quando houver poucas correspondências.
- [ ] Treino com **gsplat** `simple_trainer.py` sobre o dataset COLMAP (`--data_factor` e steps configuráveis, checkpoints).
- [ ] **Etapa de auto-calibração** (pós-SfM/treino): detecção de pessoa/pose nos frames (avaliar MediaPipe Tasks vs MMPose/RTMPose) → estimativa da altura da pessoa em unidades da cena → **fator de escala candidato** = altura real informada ÷ altura estimada, com score de confiança (nº de frames válidos, corpo inteiro visível, oclusão) → anexar ao JSON de cena (`scaleFactor`, `source: "auto-height"`, `confidence`).
- [ ] Export: **`.ply` master** (fidelidade, com SH) + **`.ksplat` web** (compressão; avaliar PlayCanvas `splat-transform` para conversão/limpeza de floaters) — decisão 2026-09-04.
- [ ] Orquestração de jobs **idempotente e retomável**: fila (arq/Celery/RQ), estado persistido por etapa (queued→extracting→sfm→training→exporting→autocal→done/error), resume a partir da última etapa válida, retry, cancelamento; **Provisioner valida o ambiente antes do job iniciar**.
- [ ] **UI do pipeline em tempo real** (WebSocket/SSE): etapa atual, % por etapa, ETA estimado, logs acessíveis (expandir/baixar), erros explicáveis com ação sugerida.
- [ ] Telemetria de qualidade: nº de imagens registradas, nº de gaussianas, PSNR de validação, tempo por etapa, resultado da auto-calibração (fator + confiança + nº de frames usados).
- [ ] Endpoint de artefatos: download/stream do `.ply`/`.ksplat` e thumbnail/preview.

**Tecnologias**: Supabase Auth, ffmpeg, COLMAP, gsplat (Apache-2.0), PyTorch, MediaPipe/MMPose (pose), FastAPI + WebSocket/SSE, Redis (fila), S3-compatível ou disco local.
**Critérios de aceite**: (a) vídeo de teste (walkthrough 30–60s) **e** conjunto de ~200 fotos do mesmo ambiente geram `.ply`+`.ksplat` visualizáveis em ≤ 1h em GPU de consumidor (RTX 30xx+); (b) COLMAP registra ≥ 70% dos frames; PSNR val ≥ ~25 na cena de referência; (c) UI mostra progresso por etapa com atualização ≤ 2s e erro de SfM explicável; (d) em vídeo com pessoa de corpo inteiro + altura informada, auto-calibração produz fator com erro ≤ 5% medido contra distância conhecida; (e) job interrompido no meio do treino retoma da última etapa válida sem reprocessar SfM; (f) usuário A não acessa jobs/artefatos do usuário B.

---

### Fase 2 — Viewer 3D interativo

**Objetivo**: viewer web fluido do splat reconstruído, com navegação e seleção, sobre a abstração de renderer decidida.

- [ ] **Interface `SplatRenderer` própria** (decisão 2026-09-04): contrato único (load, play/pause, TRS por cena, picking, qualidade) com **dois backends**:
  - **Spark** (`@sparkjsdev/spark`, WebGPU) — primário, com recursos de edição dinâmica;
  - **@mkkellogg/gaussian-splats-3d** (`DropInViewer`, WebGL2) — **fallback automático** quando WebGPU indisponível; embute splats numa `THREE.Scene` comum (mistura GLTF + splats) e suporta múltiplas cenas com TRS e reparenting para gizmos.
- [ ] Detecção de capability no boot (WebGPU? WebGL2?) → seleção automática de backend com badge visível de qualidade.
- [ ] Carregamento de `.ksplat` (web) / `.ply` (master) com progress bar, `splatAlphaRemovalThreshold` ajustável e escolha de spherical harmonics degree conforme GPU do cliente.
- [ ] Navegação: `OrbitControls` (orbit/pan/zoom) + presets de câmera; opcional: primeiro-pessoa/WASD.
- [ ] Seleção por clique: raycast — para splats, picking aproximado via centro da gaussana mais próxima do raio (ou proxy invisível); para meshes GLTF, raycast nativo do three.js.
- [ ] HUD: contagem de gaussianas, FPS, memória, backend ativo (Spark/fallback), toggle de qualidade.
- [ ] Integração com backend: listar cenas/jobs do usuário (auth), abrir cena por ID, streaming progressivo quando viável.

**Tecnologias**: three.js, Spark + @mkkellogg/gaussian-splats-3d (atrás de `SplatRenderer`), React + Vite + TypeScript, Zustand para estado.
**Critérios de aceite**: splat de ~1–3M gaussianas roda a ≥ 30 FPS em GPU média; fallback WebGL2 engatilha automaticamente em navegador sem WebGPU (teste forçado via flag); navegação sem artefatos de ordenação perceptíveis; clique seleciona objeto com feedback visual em < 100ms; troca de backend não altera o JSON de cena.

---

### Fase 3 — Inserção e manipulação de objetos 3D

**Objetivo**: adicionar GLB/glTF e splats extras à cena e manipulá-los com gizmos — **sempre em unidades reais calibradas** (Fase 4 como dependência de exibição).

- [ ] Import de **GLB/glTF** (`GLTFLoader` + `DRACOLoader`/meshopt) via upload ou biblioteca de assets.
- [ ] Import de **splats adicionais** como objetos movíveis (múltiplas cenas com TRS; reparenting de `SplatScene` a um `Object3D` controlável — suportado por ambos os backends da `SplatRenderer`).
- [ ] Gizmos: `TransformControls` (translate/rotate/scale, espaços local/world, snap configurável em unidades reais — ex.: 1 cm / 0,5 in).
- [ ] **Dimensões reais visíveis durante o posicionamento**: bounding box do objeto exibido em m/cm/mm ou ft/in (conforme unidade ativa) enquanto arrasta/edita.
- [ ] Hierarquia de cena: painel/outliner com seleção, renomear, duplicar, deletar, show/hide.
- [ ] Painel de propriedades: posição/rotação/escala numéricas na unidade ativa + dimensões do bounding box.
- [ ] Undo/redo (command stack) e persistência da cena editada (JSON de cena versionado no backend, por usuário).
- [ ] Colisão/encaixe simples: snap ao "chão" estimado do splat (plano dominante via RANSAC nos centros das gaussianas).

**Tecnologias**: three.js (`TransformControls`, `GLTFLoader`), Zustand/immer para command stack.
**Critérios de aceite**: inserir um GLB, mover/girar/escalar via gizmo e via inputs numéricos com valores reais corretos (ex.: cadeira de 0,90 m); dimensões acompanham o drag em tempo real; estado sobrevive a reload (cena restaurada do JSON); undo/redo funciona em sequência de ≥ 20 operações.

---

### Fase 4 — Sistema de escala e unidades reais (ferramenta LIVE do viewer)

**Objetivo**: calibração como **ferramenta em tempo real dentro do viewer** — disponível antes e durante qualquer inserção de objetos/imagens — combinando auto-calibração por altura com referência manual.

- [ ] **Núcleo de unidades** (`packages/units`): tipos `Length`, unidades {mm, cm, m, in, ft}, conversões exatas (base interna em mm com aritmética decimal — `big.js`), formatação localizada (pt-BR: "1,83 m"; imperial: 5' 6").
- [ ] **Trena/régua ponto-a-ponto live**: ferramenta sempre disponível no viewer (atalho + botão); clique em 2 pontos da cena → distância exibida em tempo real na unidade ativa; múltiplas medidas simultâneas, edição de pontos (arrastar) e exclusão.
- [ ] **Definir/redefinir referência a qualquer momento**: medir uma distância com a trena → "usar como referência" → informar o valor real → fator de escala recalculado e aplicado ao nó-raiz **sem reiniciar a sessão** (objetos já inseridos mantêm dimensões reais).
- [ ] **Confirmação da auto-calibração na 1ª abertura da cena**: se o job trouxe `scaleFactor` com `source: "auto-height"`, pré-aplicar e pedir confirmação guiada — sugerir 2 pontos e perguntar **"a distância entre estes pontos parece X m?"** (opções: confirmar / ajustar / medir manualmente). Se confiança baixa ou ausente, ir direto para a calibração manual guiada.
- [ ] Suporte a múltiplas calibrações (média ponderada) e exibição de erro estimado; indicador persistente no HUD do estado da escala ("calibrada · auto-altura · conf. alta" / "não calibrada").
- [ ] **Consumidores sempre em unidades reais**: inserção de objetos 3D (Fase 3) e overlays de imagem (Fase 5) operam **somente** sobre cena calibrada — dimensões reais visíveis durante o posicionamento; bloqueio amigável com CTA de calibração se a cena estiver sem escala.
- [ ] UI de unidades: seletor métrico/imperial, entrada de dimensões exatas em qualquer unidade com conversão ao vivo; preferência persistida no perfil (Supabase).
- [ ] Persistir calibração (fator, origem, confiança, pontos de referência) no JSON de cena.

**Tecnologias**: `big.js` no núcleo; testes de propriedade (round-trip de conversões); Supabase (preferências por usuário).
**Critérios de aceite**: (a) com auto-calibração por altura confirmada, medir distância conhecida da cena com erro ≤ 5%; com referência manual informada, erro ≤ 2%; (b) trena responde em < 100ms por medição e funciona durante uma sessão de edição sem reiniciar; (c) redefinir a referência no meio da edição preserva as dimensões reais dos objetos já inseridos; (d) conversão m↔ft/in round-trip exata até 0,01 mm; trocar unidade da UI não altera o modelo interno; (e) fluxo de 1ª abertura exibe o prompt de confirmação quando `source: "auto-height"` está presente.

---

### Fase 5 — Overlays de textura/imagem (cores, papéis de parede, adesivos)

**Objetivo**: aplicar imagens/texturas sobre superfícies da cena reconstruída, **com escala em unidades reais**.

- [ ] **Proxy geométrico**: splats puros não recebem textura UV — gerar malha proxy a partir da reconstrução:
  - Opção A (pipeline): treinar/derivar **2DGS ou SuGaR** (malha extraída do splat) como etapa opcional do pipeline.
  - Opção B (rápida, MVP): reconstrução Poisson/marching-cubes sobre a nuvem de centros das gaussianas (Open3D), com simplificação.
- [ ] **Decals projetivos**: projeção de imagem sobre a malha via câmera virtual do ponto de vista atual (projective texture mapping / decal geometry), com controle de posição, escala, rotação e tiling.
- [ ] Casos de uso **em unidades reais** (integra Fase 4): pintura de parede (cor sólida com mistura), papel de parede (textura tileada com **escala do padrão em cm/mm reais**), adesivos/stickers (decal único com alpha e **dimensão exata informada pelo usuário** — ex.: adesivo de 30 × 45 cm).
- [ ] Seleção de superfície: clique na malha proxy (invisível ou semi-visível) define a região alvo; máscara por plano/normal para evitar "sangramento" em quinas.
- [ ] Editor de overlay: upload de imagem, ajuste de opacidade/modo de mistura, preview em tempo real, múltiplos overlays por cena, persistência no JSON de cena.
- [ ] Render final: overlays compõem com o splat (malha proxy renderizada só com a textura do overlay, depth-tested contra o splat).

**Tecnologias**: Open3D ou SuGaR/2DGS (malha), three.js (`DecalGeometry` ou shader de projeção custom), shaders GLSL para blending.
**Critérios de aceite**: aplicar papel de parede em parede plana real da cena com alinhamento visual correto sob órbita de câmera; **escala do padrão em cm reais confere com a trena do viewer**; adesivo de dimensão exata informada (ex.: 30 cm) mede 30 cm na ferramenta; adesivo com alpha não mostra bordas; overlays persistem e recarregam.

---

### Fase 6 — Cenas dinâmicas / movimentos complexos (pesquisa → incremental)

**Objetivo**: evoluir de cenas estáticas para dinâmicas (vídeo com objetos/pessoas em movimento), de forma incremental. **Decisão 2026-09-04: monocular primeiro, com arquitetura preparada para multi-câmera** (modelo de dados de captura, orquestrador e formatos já admitem N streams sincronizados).

- [ ] Marco 0 (pesquisa): levantamento do estado da arte em dynamic 3DGS — **MoE-GS** (mixture-of-experts para dynamic Gaussian splatting, IEEE TPAMI Set/2026), 4DGS, Deformable-3DGS, SC-GS; comparar código aberto, licenças e requisitos de GPU.
- [ ] Marco 1: suporte a "dinâmico leve" — vídeo estático reconstruído + objetos GLB animados inseridos na edição (nada de treino novo).
- [ ] Marco 2: pipeline 4D **monocular**: timestamps por frame, treino deformable/4DGS, reprodução temporal no viewer (scrub de tempo).
- [ ] Marco 3: movimentos complexos via abordagem MoE (roteadores/experts por região ou por trajetória), conforme maturidade do código aberto do MoE-GS; validar custo de treino vs. ganho visual. Extensão **multi-câmera** entra aqui, sobre a arquitetura já preparada.
- [ ] Viewer: player temporal (play/pause/scrub), interpolador de câmera, orçamento de memória para sequências longas (streaming por janela temporal).

**Tecnologias**: a definir no Marco 0 (candidatos: implementações 4DGS/Deformable-GS/MoE-GS; gsplat como base de rasterização).
**Critérios de aceite (M2)**: vídeo monocular com pessoa andando gera sequência reproduzível no viewer com scrub fluido; fantasmas/artefatos de movimento visivelmente menores que a baseline estática na mesma cena; modelo de dados aceita captura multi-câmera sem migração de schema.

---

### Fase 7 — Testes e QA

**Objetivo**: confiança contínua no instalador, no pipeline e na UI (preferência do usuário: **Playwright** para UI).

- [ ] **E2E de UI com Playwright (MCP)**: fluxos críticos — **setup automatizado (com Provisioner mockado)** → criar conta → upload de vídeo/imagens + altura → acompanhamento de job em tempo real → abertura do viewer → **confirmação de auto-calibração / trena live** → inserção/manipulação de objeto com dimensões reais → aplicação de overlay → salvar/reabrir cena.
- [ ] Testes do **instalador/Provisioner**: matriz de pré-checagens simuladas (sem GPU, WSL2 desabilitado, driver antigo, sem espaço) → mensagens guiadas corretas; idempotência (rodar 2×); smoke test pós-instalação de cada componente.
- [ ] Testes de unidade: núcleo de unidades (conversões, round-trips, formatação pt-BR/imperial), reducers/command stack de edição, cálculo de fator de escala (auto e manual).
- [ ] Testes de **auto-calibração**: dataset sintético/referência com altura conhecida (pessoa de 1,80 m) → fator dentro de ±5%; casos negativos (sem pessoa, corpo parcial, oclusão) → confiança baixa + fallback para manual.
- [ ] Testes do pipeline: dataset de referência pequeno versionado (vídeo curto + conjunto de imagens + COLMAP esperado), checagem de regressão (nº imagens registradas, PSNR mínimo, nº de gaussianas dentro de faixa); **teste de resume** (matar worker no treino → retomar).
- [ ] Testes visuais: screenshots do viewer em ângulos fixos (Playwright) com tolerância de diff; cena sintética determinística para estabilidade; teste do **fallback Spark→@mkkellogg** forçando ausência de WebGPU.
- [ ] Testes de performance: FPS budget por classe de GPU, tempo de carregamento do splat, tempo de pipeline por etapa (alerta de regressão).
- [ ] Matriz de compatibilidade: Chrome/Edge (WebGPU) + Firefox/Safari (fallback WebGL2).
- [ ] QA manual guiado: checklist de aceite por fase executado a cada release.

**Tecnologias**: Playwright (via Playwright MCP no desenvolvimento), Vitest, pytest, GitHub Actions (job GPU self-hosted para pipeline, quando disponível).
**Critérios de aceite**: suite E2E verde no CI para os 6+ fluxos críticos; cobertura do núcleo de unidades ≥ 90%; regressão de pipeline detecta degradação de PSNR > 1 dB; matriz do Provisioner cobre os 4 cenários de falha simulados; teste de resume passa sem reprocessar etapas concluídas.

---

### Fase 8 — Empacotamento e polimento (contínuo / pós-MVP)

- [ ] Onboarding do usuário: tutorial interativo de captura (como filmar), calibração e edição.
- [ ] Compressão agressiva de splats para web (splat-transform/SOG), cache e CDN.
- [ ] Internacionalização (pt-BR primeiro; en-US).
- [ ] Observabilidade: métricas de jobs, erros de frontend (Sentry), analytics de uso, logs de setup do Provisioner.
- [ ] Hardening: limites de upload, quotas por usuário, limpeza de artefatos antigos.

---

## 6. Stack recomendada (com justificativa)

| Camada | Recomendação | Justificativa curta |
|---|---|---|
| Treino 3DGS | **gsplat** (nerfstudio-project) | Apache-2.0 (o repo original INRIA/graphdeco é restrito a pesquisa), CUDA otimizado, `simple_trainer` reproduz métricas do paper com mais velocidade e menos memória; wheels pré-compiladas. Nerfstudio completo só se precisarmos do ecossistema (`ns-train`, viewers) — é mais pesado. |
| SfM | **COLMAP** | Padrão-ouro, CLI scriptável, integra direto com gsplat. Alternativa futura: GLOMAP/hloc para acelerar matching em vídeos longos. |
| Extração de frames | **ffmpeg** | Ubíquo, scriptável, filtros de qualidade (dedup/blur). Instalado pelo Provisioner. |
| Setup/ambiente | **App desktop Tauri + Bootstrap/Provisioner próprio** (PowerShell + bash/WSL, idempotente) + **UI de Setup** — *decisão 2026-09-04* | Requisito central: zero-CLI. Tauri dá a experiência "instala e abre" (janela nativa leve, auto-update) e orquestra Provisioner + backend local; o Provisioner faz detecção de GPU/CUDA, instalação de dependências, verificação de saúde e relatório na UI com erros guiados. |
| Renderer de splats | **Spark (primário, WebGPU) + @mkkellogg/gaussian-splats-3d (fallback WebGL2) atrás de interface `SplatRenderer` própria** — *decisão 2026-09-04* | Spark é o renderer three.js mais moderno (WebGPU, edição dinâmica); o fallback garante compatibilidade universal. A interface própria desacopla o app do motor e torna a troca indolor. PlayCanvas/SuperSplat descartado como base: excelente editor, mas engine/ecossistema separado dificultaria a camada de edição custom. |
| Frontend | **React + Vite + TypeScript**, Zustand | Iteração rápida, tipagem forte, ecossistema three.js maduro. |
| Backend/API | **FastAPI + Redis (arq/Celery) + WebSocket/SSE** | Python casa com o pipeline (reuso de código), jobs assíncronos idempotentes/retomáveis, progresso em tempo real para setup e pipeline. |
| Auth/multiusuário | **Supabase Auth (desde a Fase 1)** — *decisão 2026-09-04* | Auth pronto (e-mail/OAuth), RLS para isolamento por usuário, perfil para preferências (unidade), MCP disponível para operação. |
| Entrega de splat | **`.ply` master + `.ksplat` web** — *decisão 2026-09-04* | `.ply` preserva fidelidade/SH (arquivo-mestre); `.ksplat` comprimido para carregamento web rápido (conversão via `splat-transform`). |
| Unidades | **Núcleo TS próprio + big.js** | Precisão decimal até mm, conversões exatas SI↔imperial, testável isoladamente, compartilhável no monorepo. |
| Auto-calibração | **Detecção de pessoa/pose nos frames (MediaPipe Tasks ou MMPose/RTMPose — escolher na Fase 1)** | Cruza altura estimada na cena com a altura real informada → fator de escala candidato + score de confiança; fallback sempre manual. |
| Malha proxy (Fase 5) | **Open3D (MVP) → SuGaR/2DGS (qualidade)** | Poisson resolve o MVP; SuGaR/2DGS dão malha fiel ao splat para overlays de alta qualidade. |
| Testes | **Playwright (MCP) + Vitest + pytest** | Preferência declarada do usuário para UI; cobertura ponta a ponta. |
| GPU dev/prod | **WSL2 + CUDA (dev Windows) / servidor GPU próprio (produção)** — *decisão 2026-09-04* | gsplat/CUDA em Windows nativo é frágil; servidor próprio dá controle de custo e fila dedicada de treino. |

---

## 7. Riscos e decisões

### Decisões tomadas (2026-09-04) — consolidadas no plano

1. **Renderer**: Spark (primário, WebGPU) com fallback @mkkellogg/gaussian-splats-3d, ambos atrás da interface `SplatRenderer` própria.
2. **Captura para cenas dinâmicas**: monocular primeiro, com arquitetura preparada para multi-câmera.
3. **Formato de entrega**: `.ply` master (fidelidade) + `.ksplat` web (compressão).
4. **Auth/multiusuário**: Supabase Auth desde a Fase 1.
5. **Infra de treino em produção**: servidor GPU próprio.
6. **Distribuição/instalador**: **app desktop Tauri** — janela nativa leve (~10 MB, WebView do Windows) encapsulando setup (Provisioner) + backend local + viewer, com auto-update; experiência "instala e abre" para usuário não-técnico.

### Riscos

- **Instalação automatizada em máquinas heterogêneas**: drivers NVIDIA variados, WSL2 não habilitado, permissões de usuário, antivírus bloqueando downloads → mitigação: pré-checagens abrangentes do Provisioner, mensagens guiadas acionáveis por componente, pacote de logs de setup para suporte, instalador idempotente e resumível.
- **Auto-calibração por altura pode falhar**: pessoa ausente no vídeo, oclusão, corpo parcialmente visível, múltiplas pessoas → mitigação: score de confiança explícito, **calibração manual (trena) sempre disponível como caminho principal/confirmatório**, e confirmação guiada na 1ª abertura mesmo quando a auto-calibração encontra fator.
- **WebGPU no viewer**: cobertura de navegadores ainda parcial (Firefox/Safari) → **coberto pela decisão do renderer**: fallback automático Spark→@mkkellogg (WebGL2) com teste forçado em CI.
- **Licenciamento**: usar apenas componentes permissivos (gsplat Apache-2.0, COLMAP BSD). Não distribuir código do 3DGS original (INRIA) em produto comercial. Validar licença de cada modelo GLB de terceiros.
- **Qualidade do SfM em vídeo real**: blur de movimento, baixa textura e autoexposição derrubam o COLMAP → mitigar com validação na ingestão, orientações de captura ao usuário e `sequential_matcher`.
- **Malha proxy imperfeita**: Poisson sobre centros de gaussianas pode gerar superfícies grosseiras em cenas esparsas → overlays podem exigir SuGaR/2DGS (custo extra de pipeline e GPU).
- **GPU do cliente**: splats grandes (3M+) derrubam GPUs fracas → compressão (.ksplat), redução de SH degree e LOD serão necessários cedo.
- **Dynamic GS é fronteira de pesquisa**: MoE-GS (TPAMI Set/2026) pode não ter código aberto maduro; Fase 6 é exploratória por design.
- **Windows como SO de dev**: todo o pipeline GPU deve rodar em WSL2/Docker; scripts devem assumir Linux.

### Decisões em aberto

1. **Biblioteca de pose/pessoa para auto-calibração**: MediaPipe Tasks (leve, roda no worker) vs MMPose/RTMPose (mais preciso, mais pesado) — decidir com benchmark na Fase 1.
