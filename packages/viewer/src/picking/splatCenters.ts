import { addVec3, dotVec3, scaleVec3, subVec3, vec3Length, type Vec3 } from '../math/vec3';
import type { Ray3 } from '../renderer/SplatRenderer';

export interface SplatCenterSample {
  index: number;
  center: Vec3;
  handleId?: string;
  opacity?: number;
}

export interface SplatCenterHit {
  index: number;
  handleId?: string;
  distance: number;
  point: Vec3;
  rayDistance: number;
}

export interface PickCentersOptions {
  maxDistance?: number;
  minOpacity?: number;
}

/**
 * Picking aproximado: gaussiana cujo centro está mais perto do raio.
 * Usado para splats quando o backend não expõe raycast nativo, e em testes.
 */
export function pickClosestSplatCenter(
  ray: Ray3,
  centers: readonly SplatCenterSample[],
  options: PickCentersOptions = {},
): SplatCenterHit | null {
  const maxDistance = options.maxDistance ?? Infinity;
  const minOpacity = options.minOpacity ?? 0;
  let best: SplatCenterHit | null = null;

  for (const sample of centers) {
    if (sample.opacity !== undefined && sample.opacity < minOpacity) {
      continue;
    }
    const toPoint = subVec3(sample.center, ray.origin);
    const t = Math.max(0, dotVec3(toPoint, ray.direction));
    const closest = addVec3(ray.origin, scaleVec3(ray.direction, t));
    const lateral = vec3Length(subVec3(sample.center, closest));
    if (lateral > maxDistance) {
      continue;
    }
    if (!best || lateral < best.distance || (lateral === best.distance && t < best.rayDistance)) {
      best = {
        index: sample.index,
        handleId: sample.handleId,
        distance: lateral,
        point: closest,
        rayDistance: t,
      };
    }
  }

  return best;
}

export function distancePointToRay(point: Vec3, ray: Ray3): number {
  const toPoint = subVec3(point, ray.origin);
  const t = Math.max(0, dotVec3(toPoint, ray.direction));
  const closest = addVec3(ray.origin, scaleVec3(ray.direction, t));
  return vec3Length(subVec3(point, closest));
}
