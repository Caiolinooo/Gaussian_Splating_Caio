import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';

import type { SplatFormat } from './SplatRenderer';

/**
 * Adapter sobre `@mkkellogg/gaussian-splats-3d` (DropInViewer).
 *
 * API documentada:
 * - `new DropInViewer({ dynamicScene, sphericalHarmonicsDegree, ... })`
 * - `addSplatScene(path, { format, splatAlphaRemovalThreshold, position, rotation, scale, showLoadingUI })`
 * - `getSplatScene(index)` → Object3D (reparent para gizmos)
 * - `SceneFormat.Ply | KSplat`
 *
 * TODOs:
 * 1. Load de buffer não é nativo — usamos `URL.createObjectURL` (sem extensão;
 *    por isso `format` é obrigatório).
 * 2. `setQuality(shDegree)` após o load pode exigir reload; aplicamos no próximo
 *    `addSplatScene` e tentamos propriedades runtime se existirem.
 * 3. Picking nativo (`viewer.raycaster.intersectSplatMesh`) não está na API do
 *    DropInViewer de forma estável — tentamos e caímos em centros.
 * 4. Remoção de uma SplatScene individual não é API de primeira classe;
 *    detach + hide.
 */
export interface MkSplatSceneLike {
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
  removeFromParent?: () => void;
}

export interface MkDropInViewerLike extends MkSplatSceneLike {
  addSplatScene(path: string, options?: Record<string, unknown>): Promise<unknown>;
  getSplatScene?(index: number): MkSplatSceneLike;
  getSplatCount?(): number;
  splatMesh?: {
    getSplatCount?: () => number;
    getSceneIndexForSplat?: (splatIndex: number) => number;
  };
  raycaster?: {
    intersectSplatMesh?: (mesh: unknown, hits: unknown[]) => void;
  };
  dispose?: () => void;
}

export interface MkModuleLike {
  DropInViewer: new (options: Record<string, unknown>) => MkDropInViewerLike;
  SceneFormat?: { Ply?: unknown; KSplat?: unknown; Splat?: unknown };
}

let testModule: MkModuleLike | null = null;

export function setMkKelloggModuleForTests(mod: MkModuleLike | null): void {
  testModule = mod;
}

export function getMkKelloggModule(): MkModuleLike {
  if (testModule) {
    return testModule;
  }
  const mod = GaussianSplats3D as unknown as MkModuleLike;
  if (!mod.DropInViewer) {
    throw new Error('API MkKellogg inesperada: DropInViewer ausente.');
  }
  return mod;
}

export function resolveMkFormat(mod: MkModuleLike, format: SplatFormat): unknown {
  const sceneFormat = mod.SceneFormat;
  switch (format) {
    case 'ply':
      return sceneFormat?.Ply ?? 0;
    case 'ksplat':
      return sceneFormat?.KSplat ?? 2;
    default: {
      const exhaustive: never = format;
      throw new Error(`Formato MkKellogg não suportado: ${String(exhaustive)}`);
    }
  }
}

export function createDropInViewer(
  mod: MkModuleLike,
  options: Record<string, unknown>,
): MkDropInViewerLike {
  return new mod.DropInViewer(options);
}
