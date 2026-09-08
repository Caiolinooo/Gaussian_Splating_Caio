# SceneIO — ingestão e exportação unificadas

Uma superfície. Não há pipeline WebGPU, pipeline 4D e pipeline de ingest em paralelo.
Toda origem (vídeo, fotos, GIF, PLY, e no futuro sequência 4D) entra em `ingest_scene`.
Toda entrega (web + arquivo interoperável) sai de `export_scene`.

Inspiração (só o que cabe no produto; **não** clonamos SuperSplat nem GaussianCrowds):

| Fonte                                   | O que adotamos agora                                                                     | O que fica contrato                           |
| --------------------------------------- | ---------------------------------------------------------------------------------------- | --------------------------------------------- |
| SuperSplat 3 / PlayCanvas WebGPU        | Um viewer, Spark quando há WebGPU, fallback WebGL2; export baixável (PLY + JSON de cena) | Streaming SOG/LOD, editor de splat no browser |
| GaussianCrowds (4DGS relightable em UE) | Schema `temporal` + `relight`, scrubber, flags SH                                        | Treino 4D, multi-luz Lumen, LOD de multidões  |

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

- **Detectar** por sufixo/conjunto (`pipeline/sceneio/detect.py`). O upload HTTP só persiste arquivos; o kind vem do detector.
- **Ingerir** sempre grava `ingest.json` no work dir (kind, paths, temporal).
- **PLY direto**: não roda COLMAP, gsplat, meshproxy nem autocal. Exporta o splat recebido.
- **GIF**: mesmo caminho de vídeo (ffmpeg → frames). GIF curto relaxa o mínimo de frames. Metadados temporais alimentam o scrubber; **não** há treino 4DGS.
- **Export**: `master.ply` (mestre) + `scene.ksplat` (web, se houver splat-transform) + `scene.json` (schema `@gs/viewer`, camelCase) + `scene.zip` (pacote para outros programas).
- **Viewer**: interface `SplatRenderer` única. Spark = caminho WebGPU; MkKellogg = WebGL2. Sem segundo viewer.
- **4D / relight**: campos opcionais no JSON de cena. `relight.mode = unsupported` até existir backend. SH baked (`hasSphericalHarmonics`) é o que o splat 3DGS já carrega.

## API

```
POST /jobs          file = vídeo | gif | ply   OU   files[] = imagens
GET  /jobs/{id}/artifacts/ply
GET  /jobs/{id}/artifacts/ksplat
GET  /jobs/{id}/artifacts/scene      → scene.json
GET  /jobs/{id}/artifacts/package    → scene.zip
```

## Código

| Papel                          | Módulo                                          |
| ------------------------------ | ----------------------------------------------- |
| Detector + ingest + export     | `pipeline/sceneio/`                             |
| Etapas do job (chamam SceneIO) | `pipeline/jobs/handlers.py`                     |
| Schema de cena                 | `packages/viewer/src/editing/sceneSchema.ts`    |
| Renderer                       | `packages/viewer/src/renderer/SplatRenderer.ts` |
