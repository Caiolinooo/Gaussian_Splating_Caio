import * as SparkNS from '@sparkjsdev/spark';

import type { SplatFormat } from './SplatRenderer';

/**
 * Adapter sobre a API pública do Spark 2.1.
 *
 * Assinaturas documentadas (sparkjs.dev, v2.1.0):
 * - `new SparkRenderer({ renderer: THREE.WebGLRenderer })`
 * - `new SplatMesh({ url, fileBytes, fileType, fileName, maxSh, raycastable, onProgress, onLoad })`
 * - `mesh.initialized: Promise<SplatMesh>`
 * - `mesh.maxSh` + `mesh.updateGenerator()`
 * - `mesh.numSplats`, `mesh.dispose()`, `mesh.raycast(raycaster, intersects)`
 *
 * TODOs onde a API ainda é frágil / não cobre o contrato 1:1:
 * 1. SparkRenderer documenta `THREE.WebGLRenderer`, não WebGPURenderer.
 *    A seleção "Spark = WebGPU" é política de produto; o host deve passar o
 *    renderer three.js real (hoje WebGL). Se no futuro Spark aceitar
 *    WebGPURenderer, troque apenas aqui.
 * 2. Não há `splatAlphaRemovalThreshold` no load. Mapeamos para
 *    `SparkRenderer.minAlpha = threshold / 255` (corte de render, não filtro de load).
 * 3. `SplatFileType` pode aparecer como enum ou string conforme o build.
 *    Tentamos o enum e caímos no fileName `scene.{format}`.
 * 4. `scale` do SplatMesh é uniforme (média xyz) — TRS não-uniforme degrada.
 * 5. `play`/`pause` temporal não existe (Fase 6) — só flag no backend.
 */
export interface SparkRendererLike {
  minAlpha?: number;
  dispose?: () => void;
}

export interface SparkSplatMeshLike {
  position: { set(x: number, y: number, z: number): unknown; x: number; y: number; z: number };
  quaternion: {
    set(x: number, y: number, z: number, w: number): unknown;
    x: number;
    y: number;
    z: number;
    w: number;
  };
  scale: { set(x: number, y: number, z: number): unknown; x: number; y: number; z: number };
  visible: boolean;
  initialized?: Promise<unknown>;
  isInitialized?: boolean;
  numSplats?: number;
  maxSh?: number;
  updateGenerator?: () => void;
  raycast?: (raycaster: unknown, intersects: unknown[]) => void;
  dispose?: () => void;
  removeFromParent?: () => void;
  forEachSplat?: (
    callback: (
      index: number,
      center: { x: number; y: number; z: number },
      scales: unknown,
      quaternion: unknown,
      opacity: number,
      color: unknown,
    ) => void,
  ) => void;
}

export interface SparkModuleLike {
  SparkRenderer: new (options: { renderer: unknown }) => SparkRendererLike;
  SplatMesh: new (options: Record<string, unknown>) => SparkSplatMeshLike;
  SplatFileType?: Record<string, unknown>;
}

export interface CreateSparkSplatMeshOptions {
  url?: string;
  fileBytes?: ArrayBuffer | Uint8Array;
  format: SplatFormat;
  maxSh: number;
  onProgress?: (event: ProgressEvent) => void;
}

let testModule: SparkModuleLike | null = null;

export function setSparkModuleForTests(mod: SparkModuleLike | null): void {
  testModule = mod;
}

export function getSparkModule(): SparkModuleLike {
  if (testModule) {
    return testModule;
  }
  const mod = SparkNS as unknown as SparkModuleLike;
  if (!mod.SparkRenderer || !mod.SplatMesh) {
    throw new Error('API Spark inesperada: SparkRenderer/SplatMesh ausentes.');
  }
  return mod;
}

export function resolveSparkFileType(mod: SparkModuleLike, format: SplatFormat): unknown {
  const table = mod.SplatFileType;
  switch (format) {
    case 'ply':
      return table?.PLY ?? table?.Ply ?? table?.ply ?? 'ply';
    case 'ksplat':
      return table?.KSPLAT ?? table?.KSplat ?? table?.ksplat ?? 'ksplat';
    default: {
      const exhaustive: never = format;
      throw new Error(`Formato Spark não suportado: ${String(exhaustive)}`);
    }
  }
}

export function createSparkSplatMesh(
  mod: SparkModuleLike,
  options: CreateSparkSplatMeshOptions,
): SparkSplatMeshLike {
  return new mod.SplatMesh({
    url: options.fileBytes ? undefined : options.url,
    fileBytes: options.fileBytes,
    fileType: resolveSparkFileType(mod, options.format),
    fileName: `scene.${options.format}`,
    maxSh: options.maxSh,
    raycastable: true,
    onProgress: options.onProgress,
  });
}
