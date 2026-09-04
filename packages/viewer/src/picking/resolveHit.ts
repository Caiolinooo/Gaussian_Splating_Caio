import type { MeshPickHit } from './meshRaycast';
import type { SplatPickHit } from '../renderer/SplatRenderer';

export type UnifiedPickKind = 'mesh' | 'splat';

export type UnifiedPickHit =
  | { kind: 'mesh'; distance: number; mesh: MeshPickHit }
  | { kind: 'splat'; distance: number; splat: SplatPickHit };

/** Escolhe o hit mais próximo entre meshes GLTF e splats. */
export function pickClosest(
  meshHits: readonly MeshPickHit[],
  splatHit: SplatPickHit | null,
): UnifiedPickHit | null {
  const mesh = meshHits[0];
  if (mesh && splatHit) {
    return mesh.distance <= splatHit.distance
      ? { kind: 'mesh', distance: mesh.distance, mesh }
      : { kind: 'splat', distance: splatHit.distance, splat: splatHit };
  }
  if (mesh) {
    return { kind: 'mesh', distance: mesh.distance, mesh };
  }
  if (splatHit) {
    return { kind: 'splat', distance: splatHit.distance, splat: splatHit };
  }
  return null;
}
