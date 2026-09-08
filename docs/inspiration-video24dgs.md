# Briefing — Video2 4DGS (inspiração para o orquestrador unificado de cena)

Documento curto para o orquestrador único do Gaussian Splatting Studio. **Não** é spec de implementação nem segundo pipeline.

`docs/unified-scene-io.md` **ainda não existe**. A linguagem abaixo alinha-se a [`tasks.md`](../tasks.md) (orquestrador único, `source_kind=video`, `SceneDocument`, `SplatRenderer` / Spark WebGPU, Fase 6) e ao contrato já planejado `SceneIO` / `ingestScene` / `exportScene` (SuperSplat 3 WebGPU + GaussianCrowds relight/4D). Um `unified-scene-io.md` futuro **não deve contradizer** este briefing: 4D = frames temporais + schema de timesteps no mesmo contrato; ComfyUI é *fonte* opcional, nunca runtime embutido.

---

## Fontes

O post [Video2 4DGS ComfyUI workflow now available](https://www.reddit.com/r/GaussianSplatting/comments/1w9x93b/video24dgs_comfyui_workflow_now_available/) (`r/GaussianSplatting`) anuncia o workflow ComfyUI de vídeo → 4DGS. O HTML do Reddit bloqueou fetch anônimo daqui (403); o slug e os artefatos públicos abaixo são o mapeamento verificável.

Não há paper no arXiv com o título literal «Video2-4DGS» / `Video24DGS`. O nome da comunidade é o *job* vídeo→4DGS. Backbone acadêmico e empacotamento ComfyUI:

| Papel | Link | Licença |
|---|---|---|
| Paper / repo oficiais **4D-GS** (canônicos + campo de deformação + timestamp) | [Wu et al., CVPR 2024](https://arxiv.org/abs/2310.08528) · [página](https://guanjunwu.github.io/4dgs/) · [hustvl/4DGaussians](https://github.com/hustvl/4DGaussians) | Apache-2.0 |
| Variante 4D nativa (primitivos 4D) | [Yang et al., ICLR 2024](https://arxiv.org/abs/2310.10642) · [fudan-zvg/4d-gaussian-splatting](https://github.com/fudan-zvg/4d-gaussian-splatting) | MIT |
| Workflow ComfyUI «Video → 4D World» (links típicos do post) | [Alexankharin/camera-comfyUI](https://github.com/Alexankharin/camera-comfyUI) · [video_to_4d_world.json](https://github.com/Alexankharin/camera-comfyUI/blob/main/workflows/video_to_4d_world.json) · registry `camera-comfyui` (publisher `alexk`) | MIT (submódulo SHARP: licença Apple, não OSI) |
| Pose + profundidade no workflow | [facebookresearch/vggt](https://github.com/facebookresearch/vggt) (VGGT, CVPR 2025) | licença Meta (não Apache) |
| Splat feed-forward por keyframe | [apple/ml-sharp](https://github.com/apple/ml-sharp) (SHARP) | licença Apple (não redistribuir como nosso código) |
| Export Comfy (mesmo contrato mental que `exportScene`) | `SaveSplats4D` → `.npz` (`canonical`, `trajectories`, `times`, `rotations?`, `static?`) e, opcional, **um `.ply` 3DGS por timestep** | — |

Irmãos do contrato `SceneIO` (não são Video2 4DGS; citados só para não divergir):

- **SuperSplat 3 WebGPU** — [playcanvas/supersplat v3.0.0](https://github.com/playcanvas/supersplat/releases/tag/v3.0.0) (2026-09-08): renderer compute WebGPU, export streamado PLY / compressed PLY / SOG / SPZ / `.ssproj`. Em [`tasks.md` §6](../tasks.md) SuperSplat **não** é a base do editor; entra em `exportScene` como *dialeto de artefato*, atrás de `SplatRenderer`.
- **GaussianCrowds (relight/4D)** — faixa planejada no mesmo `SceneDocument` (atributos de relight + timesteps). Sem repo homônimo público no levantamento; o analog acadêmico mais próximo é [CrowdSplat](https://arxiv.org/abs/2501.17792). Não abrir pipeline paralelo.

---

## 1. O que o projeto faz

Video2 4DGS (no sentido do post e do workflow ComfyUI) transforma **vídeo monocular** numa cena Gaussiana **navegável no tempo**: estima poses e profundidade por frame (VGGT), separa fundo estático de pixels dinâmicos, funde keyframes num splat de mundo (SHARP + polish) e amarra o movimento a trajetórias 3D (CoTracker3 → `BuildSplats4D`). O resultado não é um splat estático por frame isolado: é um contentor 4D — splats canônicos + trajetórias `[T, N, 3]` + `times` normalizados `0..1` — que se avalia num instante (`at_time`) e se exporta como `.npz` e/ou **sequência de `.ply` temporais**. O paper 4D-GS (Wu et al.) formaliza a mesma ideia no treino clássico: Gaussianas canônicas + deformação condicionada a **timestamps**, em vez de um 3DGS independente por frame.

---

## 2. Capacidades relevantes para NÓS

- **Ingest de vídeo temporal** — já temos `SourceKind.VIDEO` / `source_kind=video`, `ingest_video` (ffmpeg + filtro) e `manifest.json` com `fps` / `duration_s`. Falta só **timestamp por frame mantido** (não só `frame_000001.jpg` renumerado).
- **Timesteps 4D** — o schema útil é o do `GaussianSplats4D`: `times[]` monotônico, trajetórias por primitiva, fundo estático opcional. Isso é **dado de cena**, não grafo Comfy.
- **Export** — `.ply` por timestep (já falamos a língua `.ply` master) e, no futuro, o mesmo `exportScene` que SuperSplat 3 (SOG/SPZ/stream). `.npz` GSPLAT4D é *adapter* de import, não formato-mestre nosso.
- **ComfyUI como fonte opcional** — um utilizador (ou job externo) pode produzir `.npz` / pasta de `.ply` `*_t0000.ply` e entregá-los a `ingestScene`. **Não** instalamos, orquestramos nem embutimos ComfyUI, SHARP, VGGT ou o pack `camera-comfyUI`.

---

## 3. O que NÃO copiar

- UI Comfy (canvas, templates, Manager, registry).
- Grafo de nodes (`VideoPoseEstimator` → `MotionMaskFromDepth` → `VideoToFusedSplats` → `EstimateTracks` → `BuildSplats4D` → `RenderSplats4DVideo`).
- Segundo pipeline / segunda job machine («modo 4D» paralelo a `extracting→sfm→training→exporting→…`).
- SuperSplat como engine/editor (já descartado em `tasks.md`); só dialetos de ficheiro e padrões WebGPU via `SplatRenderer`.
- Vendor de SHARP / VGGT (licenças não-permissivas) nem o runtime Comfy.
- Treino 4D-GS (HexPlane/MLP) como etapa obrigatória agora — isso é Fase 6 Marco 2, no *mesmo* orquestrador.

---

## 4. Encaixe no contrato único `SceneIO`

Uma fachada, três verbos, um documento:

```
ingestScene(source) → SceneDocument
exportScene(scene)  → artefatos (.ply master + .ksplat hoje; SOG/SPZ/stream depois)
```

| Já existe | Como 4D entra *sem* pipeline novo |
|---|---|
| `source_kind=video` \| `images` | Vídeo continua `video`. 4D **não** é novo `source_kind`. |
| `pipeline/ingest/video.py` + `manifest.json` | `ingestScene` é a fachada desta etapa: frames + **`timestamps_s`** (e `t_norm` 0..1). |
| Job machine atual | Inalterada. Timesteps viajam em `extra` / manifest / `SceneDocument`. |
| `SceneDocument` v1 (`backgroundSplat`, nodes, calibration, overlays) | Extensão **aditiva**: `timesteps?: { t, uri, format }[]` no splat de fundo (ou node `splat`). Ausente ⇒ cena estática (hoje). |
| `run_export` (`.ply` + `.ksplat`) | `exportScene` de um timestep (t=0 ou t pedido) ou, no futuro, pasta `tXXXX.ply` — o mesmo exporter. |
| `SplatRenderer` + Spark WebGPU | Viewer lê o schema; scrub é Fase 6. SuperSplat 3 = I/O/WebGPU, não segundo viewer. |
| GaussianCrowds relight/4D | Mesmos `timesteps` + campos de relight no documento; **não** segundo ingest. |
| Import Comfy opcional | `ingestScene({ kind: "video4d-artifact", files })` mapeia `.npz`/`*_tN.ply` → `timesteps[]`. Sem worker Comfy. |

Regra: **4D = frames temporais + schema de timesteps**. Quem já passa em `ingestScene` / `exportScene` (vídeo Studio, imagens, artefato Comfy, export SuperSplat) não ganha fila nem UI paralela.

---

## 5. Incremento implementável agora vs contrato futuro

**Agora (schema / contrato; zero código de pipeline ou viewer neste briefing):**

1. Documentar `SceneIO` = fachada de `ingest_video` / `ingest_images` + `run_export` + `PUT /scenes` — sem nova máquina de estados.
2. No manifest de vídeo: `timestamps_s` e `t_norm` por frame *kept*, derivados de `probe.fps` (e do índice original, não só da ordem pós-dedup).
3. Reservar em `SceneDocument` (additive, v1 compatível) `timesteps` opcional e `source_kind` já existente.
4. Aceitar, no *contrato*, import passivo de sequência `*_tN.ply` (saída `SaveSplats4D`) como o mesmo `backgroundSplat` + lista temporal — implementação do parser fica para um PR de schema, não de job.

**Contrato futuro (Fase 6 / SuperSplat 3 / GaussianCrowds):**

- Treino deformable/4DGS e player (play/pause/scrub) no viewer, no mesmo job.
- `exportScene` streamado (SOG/SPZ) no dialeto SuperSplat 3, atrás de `SplatRenderer`.
- Atributos de relight 4D (faixa GaussianCrowds) no mesmo JSON.
- ComfyUI continua *produtor externo* opcional; nunca dependência do Provisioner.

---

## Fora de âmbito (este documento)

Não implementar pipeline, viewer, segundo ingest, nodes Comfy, nem `docs/unified-scene-io.md` aqui. Este ficheiro só amarra o vocabulário para o orquestrador.
