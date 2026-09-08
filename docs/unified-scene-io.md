# SceneIO — ingestão e exportação unificadas

Uma superfície. Não há pipeline WebGPU, pipeline 4D e pipeline de ingest em paralelo.
Toda origem (vídeo, fotos, GIF, PLY, e no futuro sequência 4D) entra em `ingest_scene`.
Toda entrega (web + arquivo interoperável) sai de `export_scene`.

Briefings irmãos (pesquisa; **não** são segundo pipeline):

- [`inspiration-video24dgs.md`](inspiration-video24dgs.md) — Video2 4DGS / timesteps
- [`inspiration-walls-depth.md`](inspiration-walls-depth.md) — paredes sem LiDAR + depth no forward pass

Inspiração (só o que cabe no produto; **não** clonamos os projetos):

| Fonte                                     | O que já está no código                                                                                                                                                      | O que fica contrato                                                                                                                                                                                                                                                              |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SuperSplat 3 / PlayCanvas WebGPU          | Um viewer; Spark quando há WebGPU; fallback WebGL2; export baixável (PLY + JSON de cena)                                                                                     | Streaming SOG/LOD; editor de splat no browser                                                                                                                                                                                                                                    |
| GaussianCrowds (4DGS relightable em UE)   | Schema `temporal` + `relight`; scrubber; flags SH (`relight.mode = unsupported`)                                                                                             | Treino 4D; multi-luz Lumen; LOD de multidões                                                                                                                                                                                                                                     |
| Video2 4DGS (workflow ComfyUI)            | `source_kind=video` (e GIF) já preenche `temporal` (`frameCount`, `durationS`, `fps`, `currentTime`, `sourceKind: video\|gif`); hint `.plyseq`/`.4dgs` reservado no detector | Timestamps por frame kept (`timestampsS` / `tNorm` no `ingest.json`); interchange `.npz` / `*_tN.ply` como _fonte_ opcional do hint de sequência — **sem** `source_kind` `comfy` e **sem** ComfyUI no Provisioner                                                                |
| Paredes sem LiDAR + depth no forward pass | Meshproxy já grava `export/proxy.glb` (Poisson sobre o `.ply`); overlays usam a proxy; autocal tem `DepthProvider`                                                           | Slots `dataset/depths/`, `dataset/normals/`, `export/depth/`; zip inclui proxy/depth **quando existirem**; prior monocular no **mesmo** `training` (não Spirula); attachment de depth no `SplatRenderer`. **TODO:** `ColmapDepthProvider` ainda é stub (`sample_depth` → `None`) |

```
                    ┌─────────────────────────────────────┐
  PLY / fotos /     │  SceneIO                            │
  GIF / vídeo  ──►  │   detect_source_kind()              │
  (seq. 4D depois)  │   ingest_scene()                    │
                    │        ├─ ply  → copia splat        │
                    │        ├─ gif  → ffmpeg → frames    │
                    │        ├─ video → ffmpeg → frames   │
                    │        └─ images → valida + copia   │
                    │   JobMachine (etapas únicas)        │
                    │        ply: SfM/treino/mesh/autocal │
                    │             SKIPPED                 │
                    │   export_scene()                    │
                    │        .ply + .ksplat + scene.json  │
                    │        + scene.zip                  │
                    └─────────────────────────────────────┘
```

## Contratos

- **Detectar** por sufixo/conjunto (`pipeline/sceneio/detect.py`). O upload HTTP só persiste arquivos; o kind vem do detector. Kinds: `video` \| `images` \| `gif` \| `ply`. Depth, paredes, Comfy e 4D **não** são kind.
- **Ingerir** sempre grava `ingest.json` no work dir (kind, paths, temporal).
- **PLY direto**: não roda COLMAP, gsplat, meshproxy nem autocal. Exporta o splat recebido.
- **GIF**: mesmo caminho de vídeo (ffmpeg → frames). GIF curto relaxa o mínimo de frames. Metadados temporais alimentam o scrubber; **não** há treino 4DGS.
- **Export**: `master.ply` (mestre) + `scene.ksplat` (web, se houver splat-transform) + `scene.json` (schema `@gs/viewer`, camelCase) + `scene.zip` (pacote para outros programas). Sidecars (`calibration.json`, `proxy.glb`, mapas de depth) entram no zip **quando o arquivo existir**.
- **Viewer**: interface `SplatRenderer` única. Spark = caminho WebGPU; MkKellogg = WebGL2. Sem segundo viewer.
- **4D / relight**: campos opcionais no JSON de cena. `relight.mode = unsupported` até existir backend. SH baked (`hasSphericalHarmonics`) é o que o splat 3DGS já carrega.

## Temporal (Video2 / GIF / vídeo)

O `SceneDocument.temporal` **já cobre timesteps de vídeo**. Vídeo e GIF passam por `ingest_scene` → `_temporal_from_video` e o export grava o bloco no JSON:

| Campo               | Papel agora                                          |
| ------------------- | ---------------------------------------------------- |
| `enabled`           | `true` em GIF; em vídeo se houver >1 frame e duração |
| `frameCount`        | frames kept (ffmpeg)                                 |
| `durationS` / `fps` | do probe / extract                                   |
| `currentTime`       | relógio 0–1 do scrubber (`SplatRenderer.setTime`)    |
| `sourceKind`        | `none` \| `gif` \| `video` \| `sequence`             |

Reservado no **mesmo** objeto / no `ingest.json` (ainda não no parser; **não** abrir `SourceKind`):

- `timestampsS` / `tNorm` — um valor por frame kept (índice original pós-ffmpeg, não só a ordem após dedup).
- `npzUri` — interchange Comfy `SaveSplats4D` (`.npz` com `canonical` / `trajectories` / `times`). Produtor **externo**; nunca runtime ComfyUI.
- Sequência `*_t0000.ply` / hint `.plyseq` / `.4dgs` → futuro `sourceKind: sequence` + `skips_reconstruction`, ainda um job.

`comfy` **não** é `source_kind` nem `temporal.sourceKind`. Um `.npz` no futuro cai no hint de sequência já reservado em `SEQUENCE_HINT_SUFFIXES`.

## Artefatos da mesma cena (paredes / depth)

Layout do job (`JobPaths` + sidecars opcionais). Depth/proxy **não** entram em `detect_source_kind`:

```
{work_dir}/
  input/ingest.json
  frames/kept/
  colmap/sparse/               # skip se kind=ply
  dataset/
    images/
    depths/                    # RESERVADO — prior monocular ou bake ED
    normals/                   # RESERVADO — prior monocular
  export/
    master.ply
    scene.ksplat
    scene.json
    scene.zip
    proxy.glb                  # meshproxy (já: OUTPUT_GLB_REL)
    calibration.json
    depth/                     # RESERVADO — mapas bakeados da mesma cena
```

- **`export/proxy.glb`**: o estágio `meshproxy` já escreve este path (`pipeline/meshproxy/stage.py`). Poisson sobre centros do `.ply`. Skip se Open3D ausente ou se kind=ply. Overlays/trena continuam na proxy — depth do forward pass **não** aposenta a malha.
- **`dataset/depths/`** (e `dataset/normals/`, `export/depth/`): slots reservados. `export_scene` **não** gera esses mapas hoje; o zip só inclui o que existir (hoje: ply + json + ksplat opcional + calibration).
- **TODO — `ColmapDepthProvider` é stub.** `pipeline/jobs/autocal_adapter.py`: `sample_depth` / `person_height_scene_units` devolvem `None`. Autocal cai no `HeuristicCameraDistanceProvider` e a trena no viewer continua autoritativa. Encher o stub (cameras.bin → `f_y` + depth esparsa / bake `ED` / mapa monocular) é evolução do **mesmo** hook — sem Spirula, sem segundo trainer, sem novo `source_kind`.

## API

```
POST /jobs          file = vídeo | gif | ply   OU   files[] = imagens
GET  /jobs/{id}/artifacts/ply
GET  /jobs/{id}/artifacts/ksplat
GET  /jobs/{id}/artifacts/scene      → scene.json
GET  /jobs/{id}/artifacts/package    → scene.zip
```

## Código

| Papel                          | Módulo                                                     |
| ------------------------------ | ---------------------------------------------------------- |
| Detector + ingest + export     | `pipeline/sceneio/`                                        |
| Etapas do job (chamam SceneIO) | `pipeline/jobs/handlers.py`                                |
| Schema de cena                 | `packages/viewer/src/editing/sceneSchema.ts`               |
| Renderer                       | `packages/viewer/src/renderer/SplatRenderer.ts`            |
| Proxy                          | `pipeline/meshproxy/stage.py` → `export/proxy.glb`         |
| Depth (stub)                   | `pipeline/jobs/autocal_adapter.py` → `ColmapDepthProvider` |
