import * as THREE from 'three';
import type { OrbitControls } from 'three/addons/controls/OrbitControls.js';

import { assertNever } from '../assertNever';
import type { CameraPreset } from '../types';

export interface CameraPose {
  position: THREE.Vector3;
  target: THREE.Vector3;
}

export function poseForPreset(preset: CameraPreset, distance = 6): CameraPose {
  const target = new THREE.Vector3(0, 1, 0);
  switch (preset) {
    case 'front':
      return { position: new THREE.Vector3(0, 1.6, distance), target };
    case 'side':
      return { position: new THREE.Vector3(distance, 1.6, 0), target };
    case 'top':
      return { position: new THREE.Vector3(0, distance, 0.01), target: new THREE.Vector3(0, 0, 0) };
    case 'iso':
      return {
        position: new THREE.Vector3(distance * 0.7, distance * 0.55, distance * 0.7),
        target,
      };
    default:
      return assertNever(preset);
  }
}

export function applyCameraPreset(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  preset: CameraPreset,
): void {
  const pose = poseForPreset(preset);
  camera.position.copy(pose.position);
  controls.target.copy(pose.target);
  camera.lookAt(pose.target);
  controls.update();
}

export function cameraPresetLabel(preset: CameraPreset): string {
  switch (preset) {
    case 'front':
      return 'Frente';
    case 'side':
      return 'Lado';
    case 'top':
      return 'Topo';
    case 'iso':
      return 'Isométrica';
    default:
      return assertNever(preset);
  }
}
