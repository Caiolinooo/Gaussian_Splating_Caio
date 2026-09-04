import { cloneQuat, cloneVec3, type Quat, type Vec3 } from './vec3';

/** Transformação posição / rotação (quat xyzw) / escala. */
export interface TRS {
  position: Vec3;
  rotation: Quat;
  scale: Vec3;
}

export const IDENTITY_TRS: TRS = Object.freeze({
  position: Object.freeze({ x: 0, y: 0, z: 0 }),
  rotation: Object.freeze({ x: 0, y: 0, z: 0, w: 1 }),
  scale: Object.freeze({ x: 1, y: 1, z: 1 }),
});

export function createTRS(partial?: Partial<TRS>): TRS {
  return {
    position: cloneVec3(partial?.position ?? IDENTITY_TRS.position),
    rotation: cloneQuat(partial?.rotation ?? IDENTITY_TRS.rotation),
    scale: cloneVec3(partial?.scale ?? IDENTITY_TRS.scale),
  };
}

export function cloneTRS(trs: TRS): TRS {
  return createTRS(trs);
}

export function trsEquals(a: TRS, b: TRS, epsilon = 1e-8): boolean {
  return (
    nearlyEqual(a.position.x, b.position.x, epsilon) &&
    nearlyEqual(a.position.y, b.position.y, epsilon) &&
    nearlyEqual(a.position.z, b.position.z, epsilon) &&
    nearlyEqual(a.rotation.x, b.rotation.x, epsilon) &&
    nearlyEqual(a.rotation.y, b.rotation.y, epsilon) &&
    nearlyEqual(a.rotation.z, b.rotation.z, epsilon) &&
    nearlyEqual(a.rotation.w, b.rotation.w, epsilon) &&
    nearlyEqual(a.scale.x, b.scale.x, epsilon) &&
    nearlyEqual(a.scale.y, b.scale.y, epsilon) &&
    nearlyEqual(a.scale.z, b.scale.z, epsilon)
  );
}

function nearlyEqual(a: number, b: number, epsilon: number): boolean {
  return Math.abs(a - b) <= epsilon;
}
