# `@gs/overlays`

Overlays de textura (pintura, papel de parede, adesivo) sobre a **malha proxy** de uma cena Gaussian Splatting. Splats puros não recebem UV — a textura é aplicada por **decal projetivo** (projective texture mapping) com escala em **unidades reais**.

Pacote de biblioteca: a cena hospedeira é **three.js**; o app React faz o bind depois (`UnitsPort`, loader de textura, gizmos).

## Decisão: shader custom, não `DecalGeometry`

`THREE.DecalGeometry` (addon) recorta triângulos da malha-alvo contra uma caixa e **bakeia UV 0–1** numa geometria nova. Serve para um adesivo estático, mas quebra os requisitos desta fase:

| Necessidade                                      | `DecalGeometry`                             | Shader projetivo                                  |
| ------------------------------------------------ | ------------------------------------------- | ------------------------------------------------- |
| Preview ao vivo (opacidade, blend, pose, tiling) | Rebuild da geometria a cada gesto           | Só uniforms                                       |
| Tiling físico (estampa de 10 cm)                 | Repeat não é uniform; a caixa _é_ o tamanho | `repeat = projectorMeters / patternMeters`        |
| Máscara por normal (anti-sangramento em quinas)  | Não existe                                  | `discard` se `N·(−D) < threshold`                 |
| Sticker com alpha premultiplied                  | Material Phong/Standard genérico            | `premultipliedAlpha` + discard de cobertura baixa |
| Wallpaper wrap vs clip de sticker                | UV 0–1 fixo                                 | `uKind` ramifica wrap/clip                        |

Por isso `ProjectiveDecal` usa uma **câmera ortográfica virtual** (caixa centrada no hit, eixo local −Z = projeção — a mesma convenção mental do decal) e um `ShaderMaterial` sobre a **mesma** `BufferGeometry` da proxy. Não há wrapper de `DecalGeometry` no runtime.

Referência da API rejeitada: [DecalGeometry](https://threejs.org/docs/pages/DecalGeometry.html).

## Fluxo de aplicação

1. O pipeline gera a **malha proxy** (Open3D/Poisson no MVP; SuGaR/2DGS depois) e o viewer a coloca sob um `proxyRoot` (invisível ou semi-visível).
2. O usuário clica a proxy → hit vira `transform.position` / `rotation` do projetor (normal da face → −Z local).
3. `OverlayManager.add(draft)` valida o modelo, empilha o overlay e monta um `ProjectiveDecal` em cada malha-alvo.
4. Textura chega via `textureLoader(textureRef)` (URL / asset id). Paint funciona sem mapa.
5. Gizmo/sliders chamam `preview(id, patch)`: atualiza o JSON interno e **só uniforms** (sem rebuild).
6. Render: overlay com `depthTest = true`, `depthWrite = false`, `polygonOffset` e `renderOrder ≥ 2000` — testa profundidade contra o splat e não o tapa.
7. Persistência: `serialize()` → `{ schemaVersion: 1, overlays: [...] }` no JSON de cena. `loadDocument` / `OverlayManager.parse` fazem o round-trip. A proxy pode chegar depois: `attach(scene, proxyRoot)` remonta.

```
splat (fundo) ── depth write
proxy mesh    ── geometry only (oculta)
ProjectiveDecal (shader) ── texture + blend, depth-test, sem depth write
```

## Integração com a malha proxy

- `targetSurface` casa `mesh.name` ou `mesh.userData.id`. Sem valor, o overlay cobre **todas** as `Mesh` sob `proxyRoot` (wrappers internos `gsOverlayWrapper` são ignorados).
- O wrapper reusa `target.geometry` e é filho da malha (TRS da proxy é herdado).
- Normais da proxy alimentam a máscara: em quina de 90°, `facing ≈ 0` e o fragmento some se `threshold = 0,5` (60°).
- Qualidade do overlay = qualidade da proxy. Poisson no MVP pode “derreter” quinas; SuGaR/2DGS melhoram o recorte.

## Integração com o sistema de unidades

Este pacote **não importa** `@gs/units`. Expõe `UnitsPort` (`convert`, `format`, `sceneMetersPerUnit`). O app faz o adaptador:

```ts
import { convert, formatLength, length } from '@gs/units';
import { OverlayManager, type UnitsPort } from '@gs/overlays';

const units: UnitsPort = {
  convert: (value, from, to) => Number(convert(value, from, to).toString()),
  format: (value, unit, options) => formatLength(length(value, unit), options),
  sceneMetersPerUnit: () => calibration.metersPerSceneUnit,
};
```

Convenção: `worldMeters = sceneUnits * sceneMetersPerUnit()`.

Até o bind existir, `createFallbackUnitsPort(factor)` cobre testes e preview.

### Matemática do `physicalTiling`

```
projectorMeters = projectorScene * sceneMetersPerUnit
patternMeters   = toMeters(patternSize)          // ex.: 10 cm → 0,10 m
repeatU         = projectorMeters.x / patternMeters.x
repeatV         = projectorMeters.y / patternMeters.y
```

- **Wallpaper** com `physicalSize`: tamanho de **um tile**; o frustum vem de `transform.scale`. Tiling explícito, se presente, vence o cálculo.
- **Sticker** com `physicalSize`: dimensão **exata** do adesivo (ex.: 30 × 45 cm) → `scene = meters / sceneMetersPerUnit`; UV repeat = 1.
- **Paint** com `physicalSize`: região pintada em unidade real; senão usa `transform.scale`.

Exemplo: projetor 2 m, estampa 10 cm, fator 1 m/unidade → `repeat = 20`. A trena do viewer deve medir 10 cm entre dois motivos vizinhos.

## Schema `Overlay` (v1)

```ts
type Overlay = PaintOverlay | WallpaperOverlay | StickerOverlay;

// campos comuns
{
  id: string
  kind: 'paint' | 'wallpaper' | 'sticker'
  opacity: number            // [0, 1]
  blendMode: 'normal' | 'multiply' | 'overlay'
  transform: { position, rotation /* rad, XYZ */, scale /* cena; z = profundidade */ }
  targetSurface?: string
  maskByNormal: { enabled: boolean, threshold: number }  // threshold = cos(ângulo)
  textureRef?: string        // obrigatório em wallpaper/sticker
  color?: string             // hex; obrigatório em paint
  tiling?: { repeatU, repeatV, offsetU?, offsetV? }
  physicalSize?: { width: {value, unit}, height: {value, unit} }  // unit: mm|cm|m|in|ft
}
```

Regras: sticker **exige** `physicalSize`; wallpaper exige `tiling` **ou** `physicalSize`; paint exige `color`. Switches sobre `kind` / `blendMode` usam `never` no `default`.

Documento de cena:

```json
{ "schemaVersion": 1, "overlays": [/* Overlay[] */] }
```

## API pública (resumo)

| Símbolo                                   | Papel                                                 |
| ----------------------------------------- | ----------------------------------------------------- |
| `createOverlay` / `validateOverlay`       | Modelo canônico + erros (`OverlayValidationError`)    |
| `OverlayCollection`                       | CRUD + ordem + serialize (sem three)                  |
| `OverlayManager`                          | Coleção + decals na cena + `preview` + `loadDocument` |
| `ProjectiveDecal`                         | Shader + câmera virtual + wrappers da proxy           |
| `computePhysicalRepeat` / `resolveTiling` | Escala real → UV                                      |
| `UnitsPort` / `createFallbackUnitsPort`   | Bind de unidades                                      |
| `surfaceFacing` / `passesNormalMask`      | Matemática da máscara (testável)                      |

Zustand é **peer opcional**: o manager tem `subscribe`; o app pode encapsular num store.

## Shaders

- `src/shaders/overlay.vert.glsl` / `overlay.frag.glsl` / `blending.glsl` — fonte comentada.
- `src/shaders/sources.ts` — as mesmas strings, para o `tsc` emitir JS sem plugin `?raw`.

Blend: `normal` (tint), `multiply`, `overlay` (Photoshop). Sticker: alpha premultiplied + discard `alpha < 0.002` (anti-halo de PNG).

## Testes

```bash
pnpm --filter @gs/overlays test
```

Cobre: tiling físico, round-trip JSON, sticker sem dimensão, máscara por normal.

## Pendências de validação

- `pnpm install` na raiz **não** foi executado daqui (proibido; outro agente é dono do workspace).
- `three@0.180.0` já aparece no store pnpm do monorepo, mas o export `"."` **não traz `.d.ts`**. O typecheck usa `src/three-module.d.ts` (API mínima). Quando o pacote oficial publicar tipos no export, esse shim pode ser removido.
- Testes puros (36) rodaram com o Vitest de `packages/units`.
- Integração visual (órbita + trena conferindo 10 cm / adesivo 30 cm) é da Fase 5 no app/viewer — fora deste pacote.
