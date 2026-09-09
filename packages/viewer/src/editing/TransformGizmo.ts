import * as THREE from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';

import { assertNever } from '../assertNever';
import { cloneTRS, createTRS, type TRS } from '../math/trs';

export type TransformMode = 'translate' | 'rotate' | 'scale';
export type TransformSpace = 'local' | 'world';

export interface SnapSettings {
  /** Snap de translação em unidades de cena (null = desligado). */
  translate: number | null;
  /** Snap de rotação em radianos (null = desligado). */
  rotate: number | null;
  /** Snap de escala (null = desligado). */
  scale: number | null;
}

export const DEFAULT_SNAP: SnapSettings = Object.freeze({
  translate: 0.01,
  rotate: Math.PI / 36,
  scale: 0.05,
});

export interface TransformGizmoOptions {
  mode?: TransformMode;
  space?: TransformSpace;
  snap?: Partial<SnapSettings>;
  onChange?: (trs: TRS) => void;
  onDragEnd?: (trs: TRS) => void;
  onDraggingChanged?: (dragging: boolean) => void;
}

/**
 * Wrapper de `TransformControls` (translate/rotate/scale, local/world, snap).
 * O helper precisa ser adicionado à cena three.js.
 */
export class TransformGizmo {
  private readonly controls: TransformControls;
  private readonly helper: THREE.Object3D;
  private readonly scene: THREE.Scene;
  private snap: SnapSettings;
  private readonly onChange?: (trs: TRS) => void;
  private readonly onDragEnd?: (trs: TRS) => void;
  private readonly onDraggingChanged?: (dragging: boolean) => void;

  constructor(
    camera: THREE.Camera,
    domElement: HTMLElement,
    scene: THREE.Scene,
    options: TransformGizmoOptions = {},
  ) {
    this.scene = scene;
    this.controls = new TransformControls(camera, domElement);
    this.controls.enabled = false;
    this.helper = resolveHelper(this.controls);
    this.scene.add(this.helper);
    this.snap = { ...DEFAULT_SNAP, ...options.snap };
    this.onChange = options.onChange;
    this.onDragEnd = options.onDragEnd;
    this.onDraggingChanged = options.onDraggingChanged;
    this.setMode(options.mode ?? 'translate');
    this.setSpace(options.space ?? 'world');
    this.applySnap();

    this.controls.addEventListener('change', () => {
      const trs = this.readTRS();
      if (trs) {
        this.onChange?.(trs);
      }
    });
    this.controls.addEventListener('dragging-changed', (event) => {
      const dragging = Boolean((event as { value?: unknown }).value);
      this.onDraggingChanged?.(dragging);
      if (!dragging) {
        const trs = this.readTRS();
        if (trs) {
          this.onDragEnd?.(trs);
        }
      }
    });
  }

  attach(object: THREE.Object3D): void {
    this.controls.enabled = true;
    this.controls.attach(object);
  }

  detach(): void {
    this.controls.detach();
    this.controls.enabled = false;
  }

  setMode(mode: TransformMode): void {
    switch (mode) {
      case 'translate':
      case 'rotate':
      case 'scale':
        this.controls.setMode(mode);
        return;
      default:
        assertNever(mode);
    }
  }

  setSpace(space: TransformSpace): void {
    switch (space) {
      case 'local':
      case 'world':
        this.controls.setSpace(space);
        return;
      default:
        assertNever(space);
    }
  }

  setSnap(snap: Partial<SnapSettings>): void {
    this.snap = { ...this.snap, ...snap };
    this.applySnap();
  }

  getSnap(): SnapSettings {
    return { ...this.snap };
  }

  getControls(): TransformControls {
    return this.controls;
  }

  getObject(): THREE.Object3D | undefined {
    return this.controls.object ?? undefined;
  }

  readTRS(): TRS | null {
    const object = this.controls.object;
    if (!object) {
      return null;
    }
    return cloneTRS(
      createTRS({
        position: { x: object.position.x, y: object.position.y, z: object.position.z },
        rotation: {
          x: object.quaternion.x,
          y: object.quaternion.y,
          z: object.quaternion.z,
          w: object.quaternion.w,
        },
        scale: { x: object.scale.x, y: object.scale.y, z: object.scale.z },
      }),
    );
  }

  dispose(): void {
    this.controls.detach();
    this.scene.remove(this.helper);
    this.controls.dispose();
  }

  private applySnap(): void {
    this.controls.setTranslationSnap(this.snap.translate ?? null);
    this.controls.setRotationSnap(this.snap.rotate ?? null);
    this.controls.setScaleSnap(this.snap.scale ?? null);
  }
}

function resolveHelper(controls: TransformControls): THREE.Object3D {
  const withHelper = controls as TransformControls & { getHelper?: () => THREE.Object3D };
  if (typeof withHelper.getHelper === 'function') {
    return withHelper.getHelper();
  }
  return controls as unknown as THREE.Object3D;
}
