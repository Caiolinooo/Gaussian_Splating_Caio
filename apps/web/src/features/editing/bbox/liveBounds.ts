import * as THREE from 'three';

import type { LiveBbox } from '../store/editingStore';

const _box = new THREE.Box3();
const _size = new THREE.Vector3();

/** Dimensões do bbox em espaço de mundo (metros, se o nó-raiz estiver calibrado). */
export function worldBoundingSize(object: THREE.Object3D): LiveBbox {
  _box.setFromObject(object);
  _box.getSize(_size);
  return { x: _size.x, y: _size.y, z: _size.z };
}

export function eulerDegreesFromQuaternion(q: { x: number; y: number; z: number; w: number }): {
  x: number;
  y: number;
  z: number;
} {
  const euler = new THREE.Euler().setFromQuaternion(
    new THREE.Quaternion(q.x, q.y, q.z, q.w),
    'XYZ',
  );
  const deg = THREE.MathUtils.radToDeg;
  return { x: deg(euler.x), y: deg(euler.y), z: deg(euler.z) };
}

export function quaternionFromEulerDegrees(
  x: number,
  y: number,
  z: number,
): {
  x: number;
  y: number;
  z: number;
  w: number;
} {
  const euler = new THREE.Euler(
    THREE.MathUtils.degToRad(x),
    THREE.MathUtils.degToRad(y),
    THREE.MathUtils.degToRad(z),
    'XYZ',
  );
  const q = new THREE.Quaternion().setFromEuler(euler);
  return { x: q.x, y: q.y, z: q.z, w: q.w };
}
