import { createTRS, type TRS } from '../math/trs';
import type { Quat } from '../math/vec3';

/**
 * gsplat/COLMAP usam OpenCV (Y para baixo). Three.js / Spark usam Y para cima.
 * Quaternion (1,0,0,0) = 180° no eixo X — convenção do editor Spark.
 */
export const OPENCV_TO_THREE_QUAT: Quat = Object.freeze({ x: 1, y: 0, z: 0, w: 0 });

export function isIdentityQuat(q: Quat, epsilon = 1e-8): boolean {
  return (
    Math.abs(q.x) <= epsilon &&
    Math.abs(q.y) <= epsilon &&
    Math.abs(q.z) <= epsilon &&
    Math.abs(q.w - 1) <= epsilon
  );
}

export function createOpenCvToThreeTRS(base?: Partial<TRS>): TRS {
  return createTRS({
    ...base,
    rotation: { ...OPENCV_TO_THREE_QUAT },
  });
}
