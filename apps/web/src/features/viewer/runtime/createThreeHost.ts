import type { HostObject3D } from '@gs/viewer';
import * as THREE from 'three';

/** Host three.js para o SceneManager (grafo + gizmos). */
export function createThreeHost(name: string): HostObject3D {
  const group = new THREE.Group();
  group.name = name;
  return group as unknown as HostObject3D;
}

export function asObject3D(host: HostObject3D | undefined): THREE.Object3D | null {
  return host ? (host as unknown as THREE.Object3D) : null;
}

export function resolveNodeId(object: THREE.Object3D): string | null {
  let current: THREE.Object3D | null = object;
  while (current) {
    const id = current.userData['gsNodeId'];
    if (typeof id === 'string' && id.length > 0) {
      return id;
    }
    current = current.parent;
  }
  return null;
}

export function setNodeId(object: THREE.Object3D, id: string): void {
  object.userData['gsNodeId'] = id;
}
