import * as THREE from 'three';

import type { Vec3 } from '../math/vec3';
import type { Ray3 } from '../renderer/SplatRenderer';

export interface MeshPickHit {
  object: THREE.Object3D;
  objectId: string;
  distance: number;
  point: Vec3;
  faceIndex?: number;
}

/**
 * Raycast nativo three.js para meshes GLTF (e qualquer Object3D com geometry).
 */
export function pickMeshes(ray: Ray3, roots: THREE.Object3D[], recursive = true): MeshPickHit[] {
  const raycaster = new THREE.Raycaster();
  raycaster.ray.origin.set(ray.origin.x, ray.origin.y, ray.origin.z);
  raycaster.ray.direction.set(ray.direction.x, ray.direction.y, ray.direction.z);
  const intersections = raycaster.intersectObjects(roots, recursive);
  return intersections.map((hit) => ({
    object: hit.object,
    objectId: hit.object.uuid,
    distance: hit.distance,
    point: { x: hit.point.x, y: hit.point.y, z: hit.point.z },
    faceIndex: hit.faceIndex ?? undefined,
  }));
}

export function createRayFromNdc(ndcX: number, ndcY: number, camera: THREE.Camera): Ray3 {
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), camera);
  return {
    origin: {
      x: raycaster.ray.origin.x,
      y: raycaster.ray.origin.y,
      z: raycaster.ray.origin.z,
    },
    direction: {
      x: raycaster.ray.direction.x,
      y: raycaster.ray.direction.y,
      z: raycaster.ray.direction.z,
    },
  };
}
