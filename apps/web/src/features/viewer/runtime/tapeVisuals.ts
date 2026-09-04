import * as THREE from 'three';

import type { ScenePoint } from '../../calibration/math/tapeMath';
import { midpoint3 } from '../../calibration/math/tapeMath';
import type { TapeDraft, TapeMeasure } from '../../calibration/store/tapeStore';

const POINT_RADIUS = 0.03;

export class TapeVisuals {
  readonly group = new THREE.Group();
  private readonly root: THREE.Object3D;

  constructor(root: THREE.Object3D) {
    this.root = root;
    this.group.name = 'tape-visuals';
    this.root.add(this.group);
  }

  sync(measures: readonly TapeMeasure[], draft: TapeDraft | null, hover: ScenePoint | null): void {
    while (this.group.children.length > 0) {
      const child = this.group.children[0];
      if (!child) {
        break;
      }
      this.group.remove(child);
      disposeObject(child);
    }

    for (const measure of measures) {
      this.addSegment(measure.a, measure.b, 0x38bdf8);
      this.addPoint(measure.a, 0xf8fafc, measure.id, 'a');
      this.addPoint(measure.b, 0xf8fafc, measure.id, 'b');
      this.addAnchor(midpoint3(measure.a, measure.b));
    }

    if (draft) {
      this.addPoint(draft.a, 0xeab308, 'draft', 'a');
      if (hover) {
        this.addSegment(draft.a, hover, 0xeab308);
        this.addPoint(hover, 0xeab308, 'draft', 'b');
      }
    }
  }

  dispose(): void {
    this.root.remove(this.group);
    disposeObject(this.group);
  }

  private addSegment(a: ScenePoint, b: ScenePoint, color: number): void {
    const geometry = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(a.x, a.y, a.z),
      new THREE.Vector3(b.x, b.y, b.z),
    ]);
    const material = new THREE.LineBasicMaterial({ color, depthTest: false });
    const line = new THREE.Line(geometry, material);
    line.renderOrder = 4000;
    this.group.add(line);
  }

  private addPoint(point: ScenePoint, color: number, measureId: string, end: 'a' | 'b'): void {
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(POINT_RADIUS, 12, 12),
      new THREE.MeshBasicMaterial({ color, depthTest: false }),
    );
    mesh.position.set(point.x, point.y, point.z);
    mesh.renderOrder = 4001;
    mesh.userData['gsTapeId'] = measureId;
    mesh.userData['gsTapeEnd'] = end;
    this.group.add(mesh);
  }

  private addAnchor(point: ScenePoint): void {
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(POINT_RADIUS * 0.6, 8, 8),
      new THREE.MeshBasicMaterial({ color: 0x6366f1, depthTest: false }),
    );
    mesh.position.set(point.x, point.y, point.z);
    mesh.renderOrder = 4001;
    this.group.add(mesh);
  }
}

function disposeObject(object: THREE.Object3D): void {
  object.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (mesh.geometry) {
      mesh.geometry.dispose();
    }
    const material = mesh.material;
    if (Array.isArray(material)) {
      for (const item of material) {
        item.dispose();
      }
    } else if (material) {
      material.dispose();
    }
  });
}
