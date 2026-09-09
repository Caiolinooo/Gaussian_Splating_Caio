# Plano revisado — Editor de Gaussian Splatting (SuperSplat-grade)

> Revisão do plano "Upgrade para Editor de Alta Qualidade" (2026-09-09), depois de auditar
> `@sparkjsdev/spark@2.1.0` em `node_modules` e o estado real de `packages/viewer`.
> **Conclusão: o plano original erra a causa do smearing e propõe reescrever o que a lib já faz.**

---

## 1. Auditoria: o que o Spark 2.1 JÁ FAZ

Fonte: `node_modules/.pnpm/@sparkjsdev+spark@2.1.0_three@0.180.0/node_modules/@sparkjsdev/spark/dist/{types,spark.module.js}`

| Capacidade | Onde | Status |
|---|---|---|
| Sort a cada frame por depth | `SparkRenderer.driveSort()` → `readbackDepth()` (GPU) → `sortWorker.call("sortSplats32")` → texture `ordering` | ✅ **já existe** |
| Sort em WASM, não CPU puro | `defines.d.ts`: `WASM_SPLAT_SORT = true` | ✅ |
| Sort radial vs Z-depth | `sortRadial` (default `true`), `minSortIntervalMs` | ✅ |
| Frustum culling + clip | vertex shader: `clipXY`, `if (abs(clipCenter.x) > clip) return` | ✅ |
| 2D covariance (Eigendecomposition) | `J`, `cov2D = Jᵀ·cov3D·J`, autovetores → quad instanciado | ✅ |
| Anti-aliasing de splat | `blurAmount`, `preBlurAmount`, `focalAdjustment`, `minPixelRadius` | ✅ **configurável — é a chave do smearing** |
| Formatos | `SplatFileType = PLY \| SPZ \| SPLAT \| KSPLAT \| PCSOGS \| PCSOGSZIP \| RAD` | ✅ **7 formatos** |
| SPZ read/write | `SpzReader`, `SpzWriter`, `transcodeSpz()` | ✅ |
| SOG (PlayCanvas compressed) | `pcsogs` / `pcsogszip` (+ `isPcSogs`, `tryPcSogsZip`) | ✅ |
| Fly / first-person | **`FpsMovement`** (WASD, `moveSpeed`, `shiftMultiplier`, `keycodeMoveMapping`) | ✅ |
| Double-click to focus | **`PointerControls.doublePress`** callback + `doublePressMoveSpeed` | ✅ |
| Inércia / damping | `PointerControls.moveInertia`, `rotateInertia`, `rotateSpeed`, `scrollSpeed` | ✅ |
| Orchestrador de câmera | **`SparkControls({canvas}).update(object3D, camera)`** | ✅ |
| Edição/seleção por região | **`SplatEdit` + `SplatEditSdf`** — `ALL/PLANE/SPHERE/BOX/ELLIPSOID/CYLINDER/CAPSULE/CONE`, `invert`, `softEdge`, `sdfSmooth` | ✅ |
| Recolor / opacity por região | `SplatEditRgbaBlendMode = MULTIPLY \| SET_RGB \| ADD_RGBA` | ✅ |
| Leitura de splat por splat | `mesh.forEachSplat(cb)`, `splatRgba: RgbaArray` | ✅ |
| Modificadores custom (shader) | `objectModifier`/`worldModifier` via `dyno` (GLSL gerado por grafo) | ✅ |
| LOD automático | `enableLod`, `lodSplatCount`, `lodRenderScale`, `paged` | ✅ |
| Raycast nativo em splat | `mesh.raycast(raycaster, intersects)`, `minRaycastOpacity` | ✅ |
| DoF / aperture | `focalDistance`, `apertureAngle` | ✅ |
| Edição viva | `SplatMesh({ editable: true })` | ✅ |

**Não existe no Spark:** export de vídeo, hotspots/walkthroughs anotados, Poisson/marching cubes,
decimação (merge de gaussianas), pós-processamento (bloom/tonemap/vignette).

---

## 2. Causa raiz do "smearing" na imagem — não é falta de GPU radix sort

Três causas, em ordem de probabilidade:

### 2.1 `blurAmount = 0.3` (causa #1 — correção de ~1 linha)
`spark.module.js:9874` → `this.blurAmount = options.blurAmount ?? 0.3;`

O próprio doc da option:
> *"Typically 0.3 ... in scenes trained **with anti-aliasing**. Scenes trained **without** the
> anti-aliasing tweak: this value was typically 0.3, **with anti-aliasing it is 0.0**."*

O `splatVertex` soma `blurAmount` na diagonal da covariância 2D: `a += fullBlurAmount; d += fullBlurAmount;`
Isso **infla cada gaussiana em ~0.5px de raio**. Numa cena de 124k splats a 1080p, o resultado é
exatamente o "borrão difuso" da imagem. `preBlurAmount` idem.

**Ação:** expor `blurAmount` / `preBlurAmount` / `focalAdjustment` / `maxStdDev` no `SplatQuality`
e setar `blurAmount: 0.0` (ou 0.1) quando o treino usou anti-aliasing. Filtro imediato de nitidez.

### 2.2 `focalAdjustment = 1.0` (causa #2)
> *"Higher values will tend to sharpen the splats. A value 2.0 can be used to match the behavior
> of the PlayCanvas renderer."*

PlayCanvas (mesmo time do SuperSplat) usa 2.0. Com 1.0 os splats saem sistematicamente
**subdimensionados e suavizados**.

### 2.3 Floaters de treino (causa #3 — não é renderer)
A imagem mostra streaks longos e brilhantes — assinatura clássica de **gaussianas mal-convergidas
esticadas** (floaters), não de ordem de blending errada. Coerente com o histórico: job `3ce6fee7`
rodou com **matcher sequential por bug em `_run_graph`** (66 cams, PSNR 39.17). Sorting nenhum
conserta geometria errada → por isso **ferramenta de cleanup é prioridade real** (Componente 2).

### 2.4 `maxStdDev = √8 ≈ 2.83`
Caudas longas de cada gaussiana. SuperSplat trabalha perto de √5 (2.24). Reduzir encurta as streaks.

> **Conclusão: o Componente 1 (WebGPU nativo + radix sort em WGSL) resolve um problema que não
> existe e custaria 3-5 semanas. É cortado.** O ganho de qualidade vem de tunar as 4 knobs acima
> (meio dia) e de limpar floaters (Componente 2).

---

## 3. Plano revisado — 6 componentes

### C0 — Anti-smearing real (NOVO · ~0.5 dia · entrega imediata)
1. `SplatQuality` ganha `blurAmount`, `preBlurAmount`, `focalAdjustment`, `maxStdDev`,
   `clipXY`, `falloff`, `sortRadial`, `minPixelRadius`, `minSortIntervalMs`.
2. `sparkAdapter.createSparkSplatMesh()` / `SparkBackend` repassam para `SparkRenderer`.
3. Defaults: `blurAmount: 0.0`, `focalAdjustment: 2.0`, `maxStdDev: Math.sqrt(5)`.
4. UI: slider "Nitidez" (blurAmount 0–1) + "Foco" (focalAdjustment 0.5–3) no `ViewerHud`.
5. **Verificação A/B**: screenshot antes/depois na mesma pose → comparar lado a lado.

### C1 — Corte de floaters / edição de splats (~1 semana)
Usa **`SplatEdit` + `SplatEditSdf`** do Spark, não compute shader novo.
- `packages/viewer/src/editing/SplatEditor.ts`
  - `deleteInRegion(sdf)` — remove floaters (SDF box/sphere/plane + `invert`)
  - `recolorRegion(sdf, color, blendMode)` — `SET_RGB` / `MULTIPLY` / `ADD_RGBA`
  - `setOpacityRegion(sdf, opacity)`
  - `crop(box)` — `SplatEditSdf` BOX invertido
  - `decimate(target)` — **fora do Spark**: ler `forEachSplat`, cluster por escala/posição,
    reescrever `PackedSplats` (algoritmo nosso, CPU, ~200 linhas)
- `packages/viewer/src/selection/` — seleção **por tela** que o Spark não dá:
  - `RectSelect` / `LassoSelect`: projetar centros (`forEachSplat` → câmera → NDC), teste
    ponto-em-retângulo / ponto-em-polígono. 1M splats em ~50ms no worker.
  - `SphereSelect`: usa `SplatEditSdfType.SPHERE` direto.
  - `SelectionVisuals.ts` — tint nos splats selecionados via `splatRgba: RgbaArray`.
- Cada op é um `EditorOp` no `CommandStack` existente (undo/redo de graça).

### C2 — Navegação avançada (~3 dias, era ~1 semana)
**Wiring do `SparkControls` + `FpsMovement`, não implementação própria.**
- `apps/web/src/features/viewer/runtime/FlyControls.ts` — fino wrapper sobre `FpsMovement`
  (WASD, Shift = `shiftMultiplier`, Space/Ctrl via `keycodeMoveMapping`).
- Double-click to focus → `PointerControls.doublePress` já exposto; ligar ao
  `fitOrbitToBox` do `cameraPresets.ts`.
- `CameraPath.ts` — **novo de verdade** (keyframes + Catmull-Rom + play/loop + JSON
  `TemporalCameraJson`). Spark não tem.
- `cameraPresets.ts` — bookmarks nomeados (localStorage + `SceneDocument`).

### C3 — Pós-processamento (~4 dias)
Three.js `EffectComposer` + passes (`three/addons/postprocessing/`, já disponível em three@0.180):
`RenderPass` → `UnrealBloomPass` → `ShaderPass` custom (ACES + sharpen + vignette + grading num
só shader) → `OutputPass` → `FXAAPass`.
- `packages/viewer/src/renderer/PostProcessPipeline.ts`
- `sceneSchema.ts`: `PostProcessJson` (conforme proposto, sem alterações).
- `PostProcessPanel.tsx`.

### C4 — Splat2Mesh (~1 semana) — **Opção A confirmada**
Você já indicou preferência por backend Python. Mantido:
- `pipeline/meshproxy/methods.py` — `poisson_reconstruct()` (melhorar), `marching_cubes()`,
  `ball_pivoting()`, `splat_to_pointcloud()`.
- `POST /jobs/{id}/mesh` + `MeshConverter.tsx` (progresso por WebSocket).
- Export OBJ/GLB/STL.

### C5 — UI/UX do editor (~1 semana)
Conforme proposto: `EditorToolbar`, `AppearancePanel`, `PostProcessPanel`, `CameraPathPanel`,
`MeshConvertPanel`, `HistogramPanel`, `StatsOverlay`, `editorToolStore`.
Adicionar **`OutlinerPanel` com solo/lock** e `ExportDialog`.

### Cortado
| Item do plano original | Motivo |
|---|---|
| Componente 1 (WebGPU nativo + WGSL radix sort) | Spark já faz GPU sort; causa do smearing é outra |
| Componente 8 (parsers PLY/SPZ/SOG/splat) | `SplatFileType` cobre 7 formatos; `SpzReader`/`SpzWriter` prontos |
| `importSplat.ts` multi-splat | `SplatMesh` já é nó posicionável com TRS; é wiring |

---

## 4. Ordem de execução

```
C0 (anti-smearing, 0.5d) ──> C1 (corte floaters, 1s) ──┐
                         └─> C2 (navegação, 3d) ───────┼─> C5 (UI, 1s)
                         └─> C3 (post-FX, 4d) ─────────┤
                                    C4 (splat2mesh, 1s)┘
```

**Sprint 1 (~1,5 sem):** C0 + C1 → o ganho visual que você quer, primeiro.
**Sprint 2 (~1,5 sem):** C2 + C3.
**Sprint 3 (~2 sem):** C4 + C5.

Total: **~4-5 semanas**, mas com valor visível desde a semana 1.

---

## 5. Verificação

```powershell
pnpm -r typecheck ; pnpm -r test ; pnpm lint
.\.venv\Scripts\python -m pytest pipeline
```

Manual, por componente:
- **C0**: A/B screenshot na mesma pose de câmera; streaks curtos, bordas nítidas.
- **C1**: selecionar região de floater no viewer → deletar → splat count cai, cena limpa; Ctrl+Z restaura.
- **C2**: WASD fly sem stutter; duplo-clique centraliza; camera path roda e exporta JSON.
- **C3**: bloom + ACES visíveis; toggle on/off sem perda de FPS > 15%.
- **C4**: GLB baixado abre no Blender com malha coerente.
- **C5**: todos os painéis abrem, sem console error, `pnpm -r typecheck` limpo.

---

## 6. Perguntas em aberto (respondidas na revisão)

1. **Ferramentas de seleção** — `SplatEditSdf` cobre tudo em 3D; o trabalho nosso é só a seleção
   **por tela** (rect/lasso). Fazemos rect + lasso + sphere. ✅ sem decisão pendente.
2. **Pós-processamento** — ACES + bloom + sharpen + vignette + grading. ✅ conforme recomendado.
3. **SOG/SPZ** — **ambos já suportados** (`pcsogs`, `pcsogszip`, `spz`). Zero custo. ✅
4. **Export de vídeo** — ⚠️ **decisão sua** (ver pergunta abaixo).
5. **Annotations/walkthroughs** — ⚠️ **decisão sua** (ver pergunta abaixo).
