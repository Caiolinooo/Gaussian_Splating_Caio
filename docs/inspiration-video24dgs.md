# Briefing — Video2 4DGS (inspiração para o orquestrador unificado de cena)

Documento curto para o orquestrador único do Gaussian Splatting Studio. **Não** é spec de implementação nem segundo pipeline.

Alinha-se a [`unified-scene-io.md`](unified-scene-io.md) e ao código em `pipeline/sceneio/` (`detect_source_kind` → `ingest_scene` → JobMachine única → `export_scene`). Os nomes de produto `SceneIO` / `ingestScene` / `exportScene` são essa mesma superfície. **Não contradizer** esse contrato: uma origem, um documento (`temporal` + `relight`), ComfyUI só como *fonte* opcional.

Irmão: [`inspiration-walls-depth.md`](inspiration-walls-depth.md) (depth/paredes no mesmo documento; sem `source_kind` novo).

---

## Fontes

O post [Video2 4DGS ComfyUI workflow now available](https://www.reddit.com/r/GaussianSplatting/comments/1w9x93b/video24dgs_comfyui_workflow_now_available/) (`r/GaussianSplatting`) anuncia o workflow ComfyUI de vídeo → 4DGS. O HTML do Reddit bloqueou fetch anônimo daqui (403); o slug e os artefatos públicos abaixo são o mapeamento verificável.

Não há paper no arXiv com o título literal «Video2-4DGS» / `Video24DGS`. O nome da comunidade é o *job* vídeo→4DGS. Backbone acadêmico e empacotamento ComfyUI:

| Papel | Link | Licença |
|---|---|---|
| Paper / repo oficiais **4D-GS** (canônicos + deformação + timestamp) | [Wu et al., CVPR 2024](https://arxiv.org/abs/2310.08528) · [página](https://guanjunwu.github.io/4dgs/) · [hustvl/4DGaussians](https://github.com/hustvl/4DGaussians) | Apache-2.0 |
| Variante 4D nativa (primitivos 4D) | [Yang et al., ICLR 2024](https://arxiv.org/abs/2310.10642) · [fudan-zvg/4d-gaussian-splatting](https://github.com/fudan-zvg/4d-gaussian-splatting) | MIT |
| Workflow ComfyUI «Video → 4D World» (links típicos do post) | [Alexankharin/camera-comfyUI](https://github.com/Alexankharin/camera-comfyUI) · [video_to_4d_world.json](https://github.com/Alexankharin/camera-comfyUI/blob/main/workflows/video_to_4d_world.json) · registry `camera-comfyui` (publisher `alexk`) | MIT (submódulo SHARP: licença Apple, não OSI) |
| Pose + profundidade no workflow | [facebookresearch/vggt](https://github.com/facebookresearch/vggt) (VGGT, CVPR 2025) | licença Meta (não Apache) |
| Splat feed-forward por keyframe | [apple/ml-sharp](https://github.com/apple/ml-sharp) (SHARP) | licença Apple (não redistribuir como nosso código) |
| Export Comfy (interchange, não mestre nosso) | `SaveSplats4D` → `.npz` (`canonical`, `trajectories`, `times`, `rotations?`, `static?`) e, opcional, **um `.ply` 3DGS por timestep** (`*_t0000.ply`) | — |

Irmãos do mesmo `SceneIO` (já no contrato; **não** clonamos os produtos):

- **SuperSplat 3 WebGPU** — [v3.0.0](https://github.com/playcanvas/supersplat/releases/tag/v3.0.0) (2026-09-08). [`unified-scene-io.md`](unified-scene-io.md): adotamos *um* viewer (Spark se WebGPU, MkKellogg se WebGL2) e export baixável (PLY + JSON). Streaming SOG/LOD e editor SuperSplat ficam contrato futuro. SuperSplat **não** é a base do editor (`tasks.md` §6).
- **GaussianCrowds (4DGS relightable)** — no contrato: schema `temporal` + `relight`, scrubber, flags SH (`relight.mode = unsupported` até haver backend). Treino 4D / multi-luz / LOD de multidões **não** entram agora.

---

## 1. O que o projeto faz

Video2 4DGS (post + workflow ComfyUI) transforma **vídeo monocular** numa cena Gaussiana **navegável no tempo**: estima poses e profundidade por frame (VGGT), separa fundo estático de pixels dinâmicos, funde keyframes num splat de mundo (SHARP + polish) e amarra o movimento a trajetórias 3D (CoTracker3 → `BuildSplats4D`). O resultado não é um 3DGS isolado por frame: é um contentor 4D — splats canônicos + trajetórias `[T, N, 3]` + `times` normalizados `0..1` — avaliado em `at_time` e exportado como `.npz` e/ou **sequência de `.ply` temporais**. O paper 4D-GS (Wu et al.) formaliza a mesma ideia no treino clássico: Gaussianas canônicas + deformação condicionada a **timestamps**, em vez de um 3DGS independente por frame.

---

## 2. Capacidades relevantes para NÓS

Já no contrato `SceneIO` / `ingest_scene`:

- **Ingest de vídeo temporal** — `source_kind=video` (e GIF pelo mesmo ffmpeg). `ingest_scene` já grava `ingest.json` com bloco `temporal` (`enabled`, `frameCount`, `durationS`, `fps`, `currentTime`, `sourceKind`).
- **Timesteps 4D** — 4D = essa trilha temporal + (futuro) lista de frames/artefatos, **não** pipeline novo. Reservado em `detect.py`: `.plyseq` / `.4dgs` / pasta `frame_*.ply` como *hint* de sequência; hoje um job rejeita vários `.ply` («sequências 4D ainda não são treinadas»).
- **Export** — `export_scene`: `master.ply` + `scene.ksplat` + `scene.json` (`temporal` + `relight`) + `scene.zip`. SuperSplat 3 entra como *dialeto de ficheiro*, não como segundo exporter.
- **ComfyUI como fonte opcional** — um `.npz` GSPLAT4D ou pasta `*_tN.ply` é interchange para `ingest_scene` (futuro `SEQUENCE`), nunca runtime. **Não** instalar ComfyUI, SHARP, VGGT nem `camera-comfyUI` no Provisioner.

---

## 3. O que NÃO copiar

- UI Comfy (canvas, templates, Manager, registry).
- Grafo de nodes (`VideoPoseEstimator` → `MotionMaskFromDepth` → `VideoToFusedSplats` → `EstimateTracks` → `BuildSplats4D` → `RenderSplats4DVideo`).
- Segundo pipeline / segunda JobMachine («modo 4D» ao lado de `extracting→sfm→training→exporting→…`).
- SuperSplat como engine/editor; GaussianCrowds como app UE. Só schema + interchange.
- Vendor de SHARP / VGGT (licenças não-permissivas) nem o runtime Comfy.
- Novo `source_kind` (`comfy`, `4dgs`, `video24dgs`). Vídeo continua `video`; sequência importada, quando existir, reusa o detector já reservado — sem treino 4D agora.
- Treino 4D-GS (HexPlane/MLP) como etapa obrigatória — Fase 6 Marco 2, na *mesma* máquina.

---

## 4. Encaixe no contrato único `SceneIO`

Uma superfície, como em [`unified-scene-io.md`](unified-scene-io.md):

```
detect_source_kind(files) → ingest_scene(...) → JobMachine → export_scene(...)
```

| Contrato atual | Como Video2 4DGS entra *sem* pipeline novo |
|---|---|
| `detect_source_kind` | Vídeo = `video`. Artefato Comfy (`.npz` / `*_tN.ply`) **não** é kind novo hoje; no futuro cai no hint de sequência já reservado (`.plyseq` / `.4dgs` / vários ply), ainda **um** ingest. |
| `ingest_scene` + `ingest.json` | Fachada do ffmpeg/imagens/PLY. 4D = preencher `temporal` (já) e, depois, timestamps por frame kept. |
| JobMachine única | Inalterada. PLY direto já faz skip de SfM/treino; sequência 4D importada fará o mesmo (`skips_reconstruction`). |
| `SceneDocument` + `temporal` + `relight` | `temporal.enabled` em vídeo/GIF; `relight.mode = unsupported` (faixa GaussianCrowds). Sem capítulo «comfy». |
| `export_scene` | Um timestep (t = `currentTime` ou 0) → `master.ply` / `scene.ksplat` / `scene.json` / `scene.zip`. Pasta `tXXXX.ply` é o mesmo exporter, N vezes, no futuro. |
| `SplatRenderer` | Spark WebGPU / MkKellogg. Scrub lê `temporal`; SuperSplat 3 não é segundo viewer. |
| GaussianCrowds | Mesmos `temporal` + `relight`; **não** segundo ingest. |
| ComfyUI opcional | Produtor externo → ficheiros → `ingest_scene`. Sem worker Comfy. |

Regra (igual ao contrato): **4D = frames temporais + schema `temporal`**. Quem já passa em `ingest_scene` / `export_scene` não ganha fila nem UI paralela.

---

## 5. Incremento implementável agora vs contrato futuro

**Agora** (schema / contrato; este briefing não pede código de pipeline/viewer):

1. Tratar Video2 4DGS como **inspiração de `temporal`**, não como kind. `source_kind=video` (e GIF) já alimentam `TemporalDocument`.
2. No manifest de vídeo: além de `fps`/`duration_s`, **`timestamps_s` / `t_norm` por frame kept** (índice original pós-ffmpeg, não só a ordem após dedup) — evolução do `ingest.json` já existente.
3. Documentar interchange Comfy (`*_tN.ply` / `.npz`) como *futuro* da reserva `SEQUENCE_HINT_SUFFIXES` — um PLY por job continua a regra atual.
4. Não abrir `SourceKind` novo nem embutir ComfyUI.

**Contrato futuro** (já escrito em `unified-scene-io.md`):

- Sequência 4D importada: um kind/hint, skip de reconstrução, `temporal.frameCount` = N, scrubber no viewer.
- Treino deformable/4DGS e player (Fase 6 M2) na **mesma** JobMachine.
- `export_scene` streamado (SOG/LOD SuperSplat 3) quando o contrato de streaming abrir.
- `relight` (GaussianCrowds) deixa `unsupported` só quando houver backend.
- ComfyUI permanece produtor externo; nunca dependência do Provisioner.

---

## Fora de âmbito (este documento)

Não implementar pipeline, viewer, segundo ingest, nodes Comfy, nem alterar `pipeline/sceneio/`. Só vocabulário para o orquestrador.
