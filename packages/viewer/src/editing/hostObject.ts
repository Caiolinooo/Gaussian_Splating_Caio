import { createId } from '../ids';
import type { TRS } from '../math/trs';

/**
 * Object3D mínimo (sem WebGL) para o grafo de cena e testes.
 * O app pode ligar um `THREE.Object3D` real via `bindExternal`.
 */
export interface HostObject3D {
  readonly uuid: string;
  name: string;
  visible: boolean;
  position: { x: number; y: number; z: number };
  quaternion: { x: number; y: number; z: number; w: number };
  scale: { x: number; y: number; z: number };
  parent: HostObject3D | null;
  readonly children: HostObject3D[];
  add(child: HostObject3D): void;
  remove(child: HostObject3D): void;
}

export class MinimalObject3D implements HostObject3D {
  readonly uuid: string;
  name: string;
  visible = true;
  position = { x: 0, y: 0, z: 0 };
  quaternion = { x: 0, y: 0, z: 0, w: 1 };
  scale = { x: 1, y: 1, z: 1 };
  parent: HostObject3D | null = null;
  readonly children: HostObject3D[] = [];

  constructor(name = '', uuid = createId('obj')) {
    this.name = name;
    this.uuid = uuid;
  }

  add(child: HostObject3D): void {
    if (child.parent) {
      child.parent.remove(child);
    }
    child.parent = this;
    this.children.push(child);
  }

  remove(child: HostObject3D): void {
    const index = this.children.indexOf(child);
    if (index >= 0) {
      this.children.splice(index, 1);
    }
    if (child.parent === this) {
      child.parent = null;
    }
  }
}

export function applyTRSToHost(host: HostObject3D, trs: TRS): void {
  host.position.x = trs.position.x;
  host.position.y = trs.position.y;
  host.position.z = trs.position.z;
  host.quaternion.x = trs.rotation.x;
  host.quaternion.y = trs.rotation.y;
  host.quaternion.z = trs.rotation.z;
  host.quaternion.w = trs.rotation.w;
  host.scale.x = trs.scale.x;
  host.scale.y = trs.scale.y;
  host.scale.z = trs.scale.z;
}

export function readTRSFromHost(host: HostObject3D): TRS {
  return {
    position: { x: host.position.x, y: host.position.y, z: host.position.z },
    rotation: {
      x: host.quaternion.x,
      y: host.quaternion.y,
      z: host.quaternion.z,
      w: host.quaternion.w,
    },
    scale: { x: host.scale.x, y: host.scale.y, z: host.scale.z },
  };
}
