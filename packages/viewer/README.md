# `@gs/viewer`

Pacote de viewer/edição 3D da plataforma de Gaussian Splatting.

Renderer **Spark** (`@sparkjsdev/spark`) primário com **fallback automático** `@mkkellogg/gaussian-splats-3d` (WebGL2), ambos atrás do contrato `SplatRenderer`. three.js é a cena hospedeira (splats + meshes GLTF). O app React+Vite consome este pacote e faz o bind de `@gs/units` via `UnitsPort`.

## Uso básico

```ts
import {
  createSplatRenderer,
  SceneManager,
  TransformGizmo,
  createViewerUiStore,
  createFallbackUnitsPort,
  pickMeshes,
  pickClosest,
  type UnitsPort,
} from '@gs/viewer';

const units: UnitsPort = createFallbackUnitsPort(); // app: bind de @gs/units
const sceneManager = new SceneManager({ units, name: 'Minha cena' });

const { renderer, detection } = await createSplatRenderer(
  { scene, renderer: webglRenderer },
  { detect: {/* force: 'mkkellogg' para teste de fallback */} },
);

const ui = createViewerUiStore();
ui.getState().setBackend(detection);

const handle = await renderer.load({ url: '/scans/room.ksplat', format: 'ksplat' });
renderer.addToScene(handle, scene);
renderer.setTRS(handle, {
  position: { x: 0, y: 0, z: 0 },
  rotation: { x: 0, y: 0, z: 0, w: 1 },
  scale: { x: 1, y: 1, z: 1 },
});

const gizmo = new TransformGizmo(camera, canvas, scene, {
  mode: 'translate',
  space: 'world',
  snap: { translate: 0.01 },
  onDragEnd: (trs) => sceneManager.setTRS(selectedId, trs),
});
```

Seleção automática (badge na UI):

| Capability                | Backend   | `reasonCode`      |
| ------------------------- | --------- | ----------------- |
| `navigator.gpu` + adapter | Spark     | `webgpu`          |
| só WebGL2                 | MkKellogg | `webgl2-fallback` |
| nenhum                    | erro      | `unsupported`     |

## Contrato `SplatRenderer`

```ts
interface SplatRenderer {
  readonly kind: 'spark' | 'mkkellogg';
  readonly capabilities: SplatCapabilities;

  load(source: SplatLoadSource, options?: SplatLoadOptions): Promise<SplatHandle>;
  addToScene(handle: SplatHandle, parent: SceneParent): void;
  removeFromScene(handle: SplatHandle): void;
  setTRS(handle: SplatHandle, trs: TRS): void;
  getTRS(handle: SplatHandle): TRS;
  pick(ray: Ray3, options?: SplatPickOptions): SplatPickHit | null;
  setQuality(quality: Partial<SplatQuality>): void;
  getQuality(): SplatQuality;
  play(): void;
  pause(): void;
  isPlaying(): boolean;
  getGaussianCount(handle?: SplatHandle): number;
  dispose(): void;
}

interface SplatLoadSource {
  url?: string;
  buffer?: ArrayBuffer | Uint8Array;
  format: 'ply' | 'ksplat';
}

interface SplatQuality {
  shDegree: 0 | 1 | 2 | 3;
  alphaRemovalThreshold: number; // 0–255
}
```

`createSplatRenderer(host)` detecta o backend e devolve `{ renderer, detection }`.

## Schema do JSON de cena (`schemaVersion: 1`)

```ts
interface SceneDocument {
  schemaVersion: 1;
  id: string;
  name: string;
  backgroundSplat: BackgroundSplatJson | null;
  nodes: SceneNodeJson[]; // GLB/glTF ou splats extras + TRS
  calibration: CalibrationJson; // placeholder Fase 4
  overlays: OverlayJson[]; // placeholder Fase 5
}
```

`SceneManager.toJSON()` / `fromDocument()` fazem o round-trip. Undo/redo: command stack imutável (≥ 20 ops).

## `UnitsPort`

Este pacote **não importa** `@gs/units`. Injete:

```ts
interface UnitsPort {
  convert(value: number | string, from: LengthUnit, to: LengthUnit): string;
  format(value: number | string, unit: LengthUnit, locale?: string): string;
}
```

## Scripts

```bash
pnpm --filter @gs/viewer test
pnpm --filter @gs/viewer typecheck
```

Não rode `pnpm install` na raiz só por causa deste pacote (lockfile compartilhado). Após o workspace instalar as deps, `three`, Spark e MkKellogg passam a resolver.

## TODOs / adapters (API Spark 2.1)

Ver `src/renderer/sparkAdapter.ts` e `src/renderer/mkKelloggAdapter.ts`.

1. `SparkRenderer` documenta `THREE.WebGLRenderer`, não WebGPURenderer — a escolha Spark=WebGPU é política de produto.
2. Sem `splatAlphaRemovalThreshold` no load Spark → mapeado para `minAlpha = threshold/255` (corte de render).
3. `SplatFileType` pode ser enum ou string — o adapter tenta os dois + `fileName`.
4. Scale do `SplatMesh` é uniforme (média xyz).
5. `play`/`pause` ainda são flags (Fase 6).
6. MkKellogg: buffer via `blob:` URL; sem `removeSplatScene` estável; SH após load pode exigir reload.
