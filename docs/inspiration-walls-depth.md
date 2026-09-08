# Briefing — paredes sem LiDAR + depth no forward pass

Documento de inspiração para o **orquestrador unificado de cena (`SceneIO`)**. Não é spec de implementação nem proposta de pipeline paralelo.

Alinha-se a [`docs/unified-scene-io.md`](unified-scene-io.md), [`docs/inspiration-video24dgs.md`](inspiration-video24dgs.md), `tasks.md`, `SceneDocument` / `CalibrationJson`, `pipeline/sceneio/` (`detect_source_kind` → `ingest_scene` → `export_scene`), `pipeline/meshproxy` e `pipeline/jobs/autocal.py` (`ColmapDepthProvider`). Não contradizer esses contratos.

**Regra de produto (repetida):** depth e paredes são **artefatos da mesma cena** (mapa de profundidade, malha proxy). Não viram `source_kind` novo. `detect_source_kind` classifica só captura/import: `video` | `images` | `gif` | `ply` (sequência 4D reservada em `.plyseq`/`.4dgs`, ainda um kind — ver Video2). SuperSplat 3 / GaussianCrowds / Video2 entram como **dialetos de interchange** do mesmo documento (`temporal` + `relight`), não como jobs irmãos.

---

## Fontes analisadas

| # | Post | Autor | O que demonstra |
|---|------|-------|-----------------|
| 1 | [How I improved the walls in Splat without LIDAR and without new images](https://www.reddit.com/r/GaussianSplatting/comments/1w5e0vo/how_i_improved_the_walls_in_splat_without_lidar/) | `Pitiful_Gain87` (set/2026) | Mesmas fotos; poses RealityScan/COLMAP; **mapas de depth + normal monocular** no [Spirula Studio](https://github.com/harry7557558/spirula-studio) antes do treino 3DGS. |
| 2 | [Depth from Gaussian splats in the forward pass, enough to drive DOF and volumetric fog](https://www.reddit.com/r/GaussianSplatting/comments/1w4cx5j/depth_from_gaussian_splats_in_the_forward_pass/) | `mvaligursky` (Martin Valigursky, PlayCanvas; set/2026) | O raster de splats do [PlayCanvas Engine](https://github.com/playcanvas/engine) **escreve depth linear no mesmo forward pass** (attachment extra); sem mesh de stand-in só para pós-processo. Cena demo: [superspl.at/scene/c1e6297e](https://superspl.at/scene/c1e6297e) (SplatGen_demo_addon, Shehab Mekky, CC BY 4.0). |

Comentários úteis do post 1 (não contradizem o OP):

- Depth/normal gerados em **Create Dataset** sobre pasta COLMAP (`sparse/0` + `images`); o dataset de fotos **não muda**.
- Poses do RealityScan/COLMAP foram **melhores** que o SfM nativo do Spirula (OP: poses Spirula → splat “muito blurry”).
- [PPISP](https://github.com/nv-tlabs/ppisp) / bilateral grid tratam **fotometria** (exposição/WB). Thread: isso **não** conserta nuvem esparsa em parede lisa.
- OP não sabe se o mesmo truque de depth/normal segura bem **outdoor**.

---

## 1. O que cada técnica faz

### 1.1 Paredes sem LiDAR (priors monocular de depth/normal)

O post troca o treino “só fotométrico” (RealityScan/COLMAP → Brush) por um treino **supervisionado por geometria monocular**: as mesmas imagens e as mesmas poses alimentam o [Spirula Studio](https://github.com/harry7557558/spirula-studio) (ex-[spirulae-splat](https://github.com/harry7557558/spirulae-splat)), que gera **depth map + normal map** por vista (Create Dataset; modelo de geometria escolhível) e usa esses mapas no treino 3DGS. Não há sensor LiDAR, não há segundo take de fotos e não há malha de fotogrametria como representação final — o ganho nas paredes lisas vem de **regularizar posição/orientação das gaussianas** onde o SfM é pobre (parede branca, pouca textura; o mesmo modo de falha já visto no job L4 com 3/192 imagens). A receita académica correspondente é [DN-Splatter](https://maturk.github.io/dn-splatter/) ([paper](https://arxiv.org/abs/2403.17822), [maturk/dn-splatter](https://github.com/maturk/dn-splatter)): loss de depth (com peso menor em bordas de gradiente RGB) + prior de normais, com mapas de sensor **ou** de rede monocular. O gerador citado pelo próprio Spirula é [Metric3D v2](https://github.com/YvanYin/Metric3D) ([paper](https://arxiv.org/abs/2404.15506)) via `scripts/predict_geometry.py` (`depths/`, `normals/` ao lado de `images/`).

### 1.2 Depth a partir dos splats no forward pass

Splats são geometria **blended**: não há Z-buffer clássico para DOF/fog/overlays. O workaround habitual é uma **malha stand-in** só para prepass de depth — geometria que se autoriza, se exporta e nunca se vê. No [PlayCanvas Engine](https://github.com/playcanvas/engine) (MIT), o raster de GSplat **escreve depth linear como attachment extra no mesmo forward pass** que escreve cor, com o **mesmo blend premultiplied**; o resultado é uma média ponderada por cobertura cujos pesos somam 1 sozinhos — sem segundo pass de geometria. O detalhe que o autor destaca: **média dos recíprocos (`1/z`)**, não da depth linear; média de `z` com cobertura parcial é puxada pelo far clip para um valor onde **não existe superfície**. Isso chega para DOF e fog volumétrico que termina nos splats; bordas finas continuam imperfeitas (um `z` por pixel não descreve cobertura semi-transparente). A linha oficial do nosso trainer já tem o análogo CUDA: [gsplat `rasterization`](https://docs.gsplat.studio/main/apis/rasterization.html) com `render_mode` `D` / `ED` / `RGB+D` / `RGB+ED` — depth acumulada `Σ wᵢ zᵢ` vs **expected** `(Σ wᵢ zᵢ) / (Σ wᵢ)` (sem “zero depth leak” do fundo). O paper citado pelo próprio PlayCanvas ([issue #7484](https://github.com/playcanvas/engine/issues/7484)) para depth espacialmente variável **dentro** do splat é [RaDe-GS](https://arxiv.org/abs/2406.01467) ([HKUST-SAIL/RaDe-GS](https://github.com/HKUST-SAIL/RaDe-GS)). Distinguir: [PR #8581](https://github.com/playcanvas/engine/pull/8581) é **depth-test** contra geometria opaca (`sceneDepthMapLinear`); o post é **depth-write** no attachment do splat.

---

## 2. Capacidades relevantes para nós (encaixe no pipeline existente)

Não abrir um segundo grafo. O job continua

`queued → extracting → sfm → training → exporting → meshproxy → autocal → done`

e o documento de cena continua `backgroundSplat` + `nodes` + `calibration` + `overlays` + os campos aditivos `temporal` / `relight` de `pipeline/sceneio/document.py` (viewer schema em `packages/viewer/src/editing/sceneSchema.ts`).

### 2.1 `meshproxy` / paredes

Hoje `pipeline/meshproxy` faz Poisson sobre **centros** do `.ply` mestre (`export/master.ply` → `export/proxy.glb`), com skip `OPEN3D_UNAVAILABLE` — nunca erro. `tasks.md` §5 Fase 5 e o README de `@gs/overlays` já dizem: **qualidade do overlay = qualidade da proxy**; Poisson “derrete” quinas; evolução prevista é SuGaR/2DGS, não um trainer irmão.

O post 1 ataca a **causa** da proxy ruim em indoor: gaussianas instáveis em parede lisa. O encaixe correto é **priors no estágio `training` já existente** (gsplat), não “rodar Spirula e importar outro `.ply`”. Mapas monocular (`dataset/depths/`, `dataset/normals/`, keyed pelo `frame_id` do ingest/COLMAP) são insumos opcionais do **mesmo** dataset COLMAP (`colmap/sparse` + frames). A proxy continua o estágio `meshproxy`: centros mais planários / normais mais usáveis (`reconstruct.prepare_cloud` já prefere normais do PLY) → melhor `proxy.glb` para wallpaper/sticker/`maskByNormal`.

Não substituir a proxy por splat-depth. Overlays projetam sobre **triângulos** (`ProjectiveDecal` reusa `BufferGeometry` da proxy). O próprio fio do post 2 (e o comentário no LinkedIn do autor) deixa o stand-in de depth obsoleto para **pós-processo**, e **não** para colisão, trena, navmesh ou decal.

### 2.2 Depth para calibração e overlays

`pipeline/autocal/depth.py` já define o contrato: `DepthProvider.sample_depth(frame_id, x_norm, y_norm) → Z + f_y`. A fórmula é `H_scene = Δv · Z / f_y`. `ColmapDepthProvider` (`pipeline/jobs/autocal_adapter.py`) é **stub** (`sample_depth` → `None`); produção cai em `HeuristicCameraDistanceProvider` e baixa `c_depth`. A trena no viewer continua autoritativa (`CalibrationJson.source`: `auto-height` | `manual` | `none`).

Dois fills do **mesmo** hook, sem novo estágio obrigatório:

1. **Agora (calibração):** amostrar depth **expected** do splat já treinado (`gsplat` `RGB+ED` nas poses COLMAP) **ou** o mapa monocular alinhado ao frame — e plugar em `run_auto_calibration(..., depth_provider=...)`. Falha → o mesmo fallback que já existe; o job **não** cai.
2. **Viewer / overlays:** `@gs/overlays` já faz `depthTest = true`, `depthWrite = false` contra o splat. O post 2 justifica um **attachment de depth linear no `SplatRenderer`** (Spark primário; MkKellogg fallback) para o teste de profundidade e para efeitos, **sem** segunda cena PlayCanvas. Spark já tem exemplos de [Depth of Field](https://sparkjs.dev/examples/#depth-of-field) e [Render Cube Depthmap](https://sparkjs.dev/examples/#render-cube-depthmap) — estender a **interface** atual, não trocar o motor (`tasks.md` §6: SuperSplat descartado como **base** do viewer).

### 2.3 Qualidade de superfície

Cadeia única, três alavancas já nomeadas no plano:

| Alavanca | Onde | O que os posts acrescentam |
|----------|------|----------------------------|
| Prior geométrico no treino | `pipeline/train` (gsplat) | Depth/normal monocular no **mesmo** `simple_trainer` / raster `RGB+ED`; receita DN-Splatter, não binário Spirula (GPLv3). |
| Proxy | `pipeline/meshproxy` | Poisson MVP; futuro TSDF/SuGaR/2DGS **sobre** depth rasterizada (RaDe-GS / `ED`), ainda gravando `export/proxy.glb`. |
| Overlay + escala | `@gs/overlays` + autocal + trena | Wallpaper em cm reais continua na proxy; depth do splat só estabiliza o teste de profundidade e o `DepthProvider`. |

PPISP / bilateral grid (comentários do post 1; [paper PPISP](https://arxiv.org/abs/2601.18336), [nv-tlabs/ppisp](https://github.com/nv-tlabs/ppisp), [BilaReF](https://radiancefields.com/bilateral-guided-radiance-field-processing)) são **fotometria**. Podem entrar depois no treino gsplat como correção de exposição; **não** são o caminho de paredes.

---

## 3. O que NÃO copiar

- **Hardware LiDAR** (iPhone, scanner, dataset RGB-D). O ganho do post 1 é monocular. DN-Splatter usa sensor quando existe; nós não exigimos.
- **RealityScan / Metashape como dependência.** O OP já aceita COLMAP. Nosso SfM é COLMAP (`source_kind` `video` | `images` | `gif`). RealityScan não entra no Provisioner.
- **Spirula Studio como segundo trainer.** App completo, SfM próprio, Vulkan, **GPLv3** — incompatível com “mais um `simple_trainer`”. Não clonar, não shell-out, não segundo job `training_spirula`. Copiar só a **ideia**: mapas `depths/` + `normals/` no dataset COLMAP.
- **Segundo renderer.** PlayCanvas / SuperSplat / SuperSplat Viewer ficam no **interchange** (`ingest_scene` / `export_scene`), não substituem Spark + `@mkkellogg` atrás de `SplatRenderer` (`tasks.md` §7 decisão 1; `unified-scene-io.md`: um viewer).
- **Segundo treino / segundo `.ply`.** Um `master.ply`, um `scene.ksplat`, uma proxy. Depth/normal são insumos ou saídas do **mesmo** grafo.
- **Novo `source_kind`.** Não criar `lidar`, `depth`, `spirula`, `supersplat`, `4dgs`. O detector já cobre `video` | `images` | `gif` | `ply`. Interchange estrangeiro vira a **mesma** `SceneDocument`.
- **Aposentar `meshproxy`.** Depth do forward pass mata o stand-in **de pós-processo**, não a malha de overlay/trena/gizmo.
- **Média crua de `z` no attachment.** Copiar o aviso do post 2: recíprocos (viewer) ou expected-depth normalizado por alpha (gsplat `ED`). Não `D` acumulado com fundo 0.
- **PPISP como “fix de parede”.** Fotometria ≠ geometria.

---

## 4. Encaixe no contrato único `SceneIO`

Uma superfície, três verbos — os nomes Python de `pipeline/sceneio/` são o contrato; camelCase é o mesmo par no texto de produto:

```
detect_source_kind(paths) → SourceKind          # video | images | gif | ply
ingest_scene(source)      → SceneIngestResult   # (= ingestScene)
export_scene(scene)       → SceneExportResult   # (= exportScene)
```

| Símbolo | Papel (já em `unified-scene-io.md`) |
|---------|--------|
| `SceneIO` | Uma superfície. Não há pipeline WebGPU, 4D e ingest em paralelo. |
| `ingest_scene` | Vídeo / GIF / fotos / PLY → `ingest.json` + frames ou splat. SuperSplat 3 / GaussianCrowds / Video2 são **dialetos** do mesmo documento, não kinds novos. |
| `export_scene` | `master.ply` + `scene.ksplat` + `scene.json` + `scene.zip` (e, se existirem, sidecars). |

`source_kind` é só **captura/import**. 4D = `temporal` (`inspiration-video24dgs.md`: frames + timesteps; `temporal.sourceKind` é `video`/`gif`/`none`). Relight = `relight` (`mode: "unsupported"` até haver backend; GaussianCrowds não abre job). WebGPU = Spark atrás de `SplatRenderer`, não um `source_kind`.

### Artefatos da mesma cena (não ramos)

Layout `JobPaths` + sidecars **opcionais**. Depth/proxy **não** entram em `detect_source_kind`:

```
{work_dir}/
  input/ingest.json            # SceneIO (kind, paths, temporal)
  frames/kept/                 # ingest vídeo/GIF/imagens
  colmap/sparse/               # SfM (skip se kind=ply)
  dataset/
    images/
    depths/                    # opcional — prior monocular ou ED bakeado
    normals/                   # opcional — prior monocular
  export/
    master.ply                 # splat canónico
    scene.ksplat               # web (se splat-transform)
    scene.json                 # SceneDocument camelCase (export_scene)
    scene.zip                  # pacote interoperável
    proxy.glb                  # meshproxy (overlays)
    calibration.json           # autocal → CalibrationJson
    depth/                     # opcional — mapas bakeados da MESMA cena
```

No JSON (`schemaVersion` 1, `build_scene_document`), depth/proxy **não** viram `SceneNodeKind` nem `source_kind`. A proxy é o alvo dos overlays (nó `glb` de trabalho, se visível). Depth é sidecar no disco / no zip, no **mesmo** `id` de cena:

```text
SceneDocument          # sceneio.document / @gs/viewer
  backgroundSplat      → master.ply / scene.ksplat
  nodes[]              → GLB / splats extra
  calibration          → scaleFactor + source auto-height|manual|none
  overlays[]           → paint|wallpaper|sticker sobre a proxy
  temporal             → 4D / Video2 / GIF (não é depth)
  relight              → GaussianCrowds (não é parede)
```

Sidecars no `export_scene` / `scene.zip` (hoje o zip já leva ply + json + ksplat + `calibration.json`; proxy e depth entram **quando existirem**, como a calibração):

- `proxy.glb` — malha da mesma cena
- `dataset/depths/*` ou `export/depth/*` — mapas da mesma cena
- `dataset/normals/*` — priors de treino da mesma cena

Como os dialetos mapeiam **sem** kind novo:

- **SuperSplat 3 WebGPU** — PLY/SOG/SPZ entram como `source_kind=ply` (SfM/treino skipped) ou como dialeto de `export_scene`. Collision `.glb` / `sceneDepthMap` do [supersplat-viewer](https://github.com/playcanvas/supersplat-viewer) mapeiam para `proxy.glb` / sidecars de depth. Sem engine PlayCanvas no runtime.
- **GaussianCrowds 4D / relight** — mesmos `temporal` + `relight`. Depth/paredes são por-frame da **mesma** trilha (`depths/` alinhado a `timestamps`), não um job “crowd”.
- **Video2 4DGS** — `source_kind=video` (já). Timesteps no documento; um mapa de depth por timestep se existir. ComfyUI continua produtor externo (`inspiration-video24dgs.md`).

`export_scene` não escolhe um “sabor” de cena. Import SuperSplat/Crowds/Video2 **não** dispara um segundo grafo só para paredes.

---

## 5. Incremento implementável agora vs contrato futuro

### Agora (sem novo renderer, sem novo trainer, sem novo `source_kind`)

1. **Reservar slots de artefato** no job/SceneIO: `dataset/depths/`, `dataset/normals/`, `export/depth/`, e chaves opcionais `proxy_glb` (já) + `depth_maps` / `normal_maps` no outcome do estágio. Ausência = no-op. Meshproxy e autocal já sobrevivem a skip.
2. **Encher `ColmapDepthProvider`** (deixar de ser stub): `cameras.bin` → `f_y`; amostrar (a) depth esparsa COLMAP se existir, ou (b) um bake `ED` pós-`exporting` nas poses registadas, ou (c) o mapa monocular se o estágio opcional o tiver escrito. Continua a regra: falha → `source: "none"` + aviso da trena; **nunca** derruba o job.
3. **Manter Poisson** como MVP. Se o PLY vier com normais mais estáveis (treino futuro com prior), `prepare_cloud` já as usa. Não exigir Open3D novo nem TSDF neste incremento.
4. **Viewer:** overlays e trena continuam na proxy. Contrato `SplatRenderer` pode ganhar um método opcional de depth (`readLinearDepth` / attachment) **quando** Spark expuser; MkKellogg ignora. Não portar o compute raster do PlayCanvas.
5. **Documentar só** (este ficheiro): priors monocular e expected-depth são evolução do **mesmo** `training` / `SplatRenderer`, não fases novas da job machine.

### Contrato futuro (mesmo `SceneIO`, sem ramificar)

`ingest_scene` / `export_scene` **já existem**. O futuro é sidecars + qualidade, não uma segunda fachada.

1. **`export_scene` / `scene.zip`** passam a incluir `proxy.glb` e mapas de depth **quando o job os tiver** (mesmo padrão de `calibration.json`). SuperSplat 3 / Crowds / Video2 continuam dialetos do mesmo `SceneDocument`; o viewer não pergunta “de que pipeline veio”.
2. **Prior no `training` gsplat** (Apache-2.0, já escolhido): loss de depth/normal estilo DN-Splatter sobre mapas Metric3D (ou equivalente permissivo) gerados **depois do SfM**, no worker, como passo opcional **dentro** de `training` ou como pré-passo do dataset — ainda no mesmo job. Sem binário GPLv3. Kind `ply` (import) **não** ganha esse prior — não há treino.
3. **`meshproxy` v2:** TSDF / SuGaR / 2DGS alimentado por depth `ED` ou RaDe-GS rasterizada do **nosso** `.ply`, ainda em `export/proxy.glb`. Overlays não mudam de API.
4. **`SplatRenderer`:** attachment de depth linear no forward pass (média de recíprocos ou expected), para overlays/`depthTest` e efeitos. Continua Spark | MkKellogg. SuperSplat 3 é formato de **ficheiro**, não backend (`unified-scene-io.md`).
5. **4D:** cada timestep reusa o mesmo par (splat, depth, proxy), no `temporal` já reservado. Relight (`relight.mode`) não duplica geometria de parede.

### Ordem sugerida (quando for hora de código)

`ColmapDepthProvider` real → slots de artefato no export/SceneIO → (opcional) gerador monocular no dataset → loss no gsplat → depth attachment no `SplatRenderer` → meshproxy TSDF. Cada passo é skippable; o grafo não ramifica.

---

## Fontes oficiais e papers citados (posts + linha direta)

### Post 1 — paredes / priors

- [Spirula Studio](https://github.com/harry7557558/spirula-studio) (GPLv3; **não** vendorar) — GUI/CLI, Create Dataset, depth/normal, meshing.
- [spirulae-splat](https://github.com/harry7557558/spirulae-splat) — formato COLMAP `images/` + `depths/` + `normals/`; `predict_geometry.py`.
- [Metric3D / Metric3D v2](https://github.com/YvanYin/Metric3D) — [v1](https://arxiv.org/abs/2307.10984), [v2](https://arxiv.org/abs/2404.15506).
- [DN-Splatter](https://maturk.github.io/dn-splatter/) — [arXiv:2403.17822](https://arxiv.org/abs/2403.17822), [maturk/dn-splatter](https://github.com/maturk/dn-splatter); [AGS-Mesh](https://arxiv.org/abs/2411.19271).
- [PPISP](https://research.nvidia.com/labs/sil/projects/ppisp/) — [arXiv:2601.18336](https://arxiv.org/abs/2601.18336), [nv-tlabs/ppisp](https://github.com/nv-tlabs/ppisp) (fotometria, não geometria).
- [Bilateral Guided Radiance Field Processing](https://radiancefields.com/bilateral-guided-radiance-field-processing) (thread do post 1).
- [RealityScan](https://www.capturingreality.com/realityscan) — citado pelo OP para poses; **fora** do nosso stack.

### Post 2 — depth no forward pass

- [PlayCanvas Engine](https://github.com/playcanvas/engine) (MIT) — GSplat compute / `sceneDepthMapLinear`.
- [GSplat depth-based postprocessing](https://github.com/playcanvas/engine/issues/7484) (mvaligursky).
- [PR #8581 — depth-test do raster compute](https://github.com/playcanvas/engine/pull/8581) (ler vs. **escrever** depth).
- [SuperSplat](https://github.com/playcanvas/supersplat) · [supersplat-viewer](https://github.com/playcanvas/supersplat-viewer) · [Splat data format](https://developer.playcanvas.com/user-manual/gaussian-splatting/rendering-architecture/splat-data-format/).
- [RaDe-GS](https://arxiv.org/abs/2406.01467) — [HKUST-SAIL/RaDe-GS](https://github.com/HKUST-SAIL/RaDe-GS) (depth espacialmente variável; citado no #7484).
- [gsplat rasterization](https://docs.gsplat.studio/main/apis/rasterization.html) — `D` / `ED` / `RGB+ED`; [migração de depth](https://docs.gsplat.studio/main/migration/migration_legacy.html).
- [gsplat#60 — depth no forward](https://github.com/nerfstudio-project/gsplat/issues/60) (histórico).
- [Spark — Depth of Field](https://sparkjs.dev/examples/#depth-of-field) · [Render Cube Depthmap](https://sparkjs.dev/examples/#render-cube-depthmap) (motor que **já** escolhemos).

### Âncoras internas (não contradizer)

- Job machine e artefactos: `pipeline/jobs/paths.py`, `pipeline/jobs/handlers.py` (`handle_meshproxy`, `handle_autocal`).
- Proxy: `pipeline/meshproxy/stage.py` (`export/proxy.glb`), `pipeline/meshproxy/__init__.py`.
- Autocal: `pipeline/jobs/autocal.py`, `pipeline/autocal/depth.py`, `ColmapDepthProvider` stub.
- Cena / overlays: `sceneSchema.ts`, `@gs/overlays` README (proxy + `depthTest`).
- Renderer: `SplatRenderer` = Spark | MkKellogg; SuperSplat **não** é o runtime (`tasks.md` §6–§7, `unified-scene-io.md`).
- `source_kind`: `detect_source_kind` → `video` | `images` | `gif` | `ply` (`pipeline/sceneio/detect.py`). Depth/paredes **não** são kind.
- 4D / relight: `temporal` + `relight` no mesmo documento (`inspiration-video24dgs.md`).
