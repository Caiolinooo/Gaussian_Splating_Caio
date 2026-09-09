import * as THREE from 'three';
import type { OrbitControls } from 'three/addons/controls/OrbitControls.js';

import { assertNever } from '../assertNever';
import type { CameraPreset } from '../types';

export interface CameraPose {
  position: THREE.Vector3;
  target: THREE.Vector3;
}

export interface WorldBoxLike {
  min: { x: number; y: number; z: number };
  max: { x: number; y: number; z: number };
}

export function poseForPreset(
  preset: CameraPreset,
  distance = 6,
  target = new THREE.Vector3(0, 1, 0),
): CameraPose {
  const look = target.clone();
  switch (preset) {
    case 'front':
      return { position: look.clone().add(new THREE.Vector3(0, distance * 0.08, distance)), target: look };
    case 'side':
      return { position: look.clone().add(new THREE.Vector3(distance, distance * 0.08, 0)), target: look };
    case 'top':
      return { position: look.clone().add(new THREE.Vector3(0, distance, 0.01)), target: look };
    case 'iso':
      return {
        position: look.clone().add(new THREE.Vector3(distance * 0.7, distance * 0.55, distance * 0.7)),
        target: look,
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
  const target = controls.target.clone();
  const currentDist = camera.position.distanceTo(target);
  const distance = currentDist > 0.15 ? currentDist : 6;
  const pose = poseForPreset(preset, distance, target);
  camera.position.copy(pose.position);
  controls.target.copy(pose.target);
  camera.lookAt(pose.target);
  controls.update();
}

export function fitOrbitToBox(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  box: WorldBoxLike,
  padding = 1.45,
): boolean {
  const min = new THREE.Vector3(box.min.x, box.min.y, box.min.z);
  const max = new THREE.Vector3(box.max.x, box.max.y, box.max.z);
  if (!Number.isFinite(min.x) || !Number.isFinite(max.x) || min.distanceTo(max) < 1e-4) {
    return false;
  }
  const size = new THREE.Vector3().subVectors(max, min);
  const center = new THREE.Vector3().addVectors(min, max).multiplyScalar(0.5);
  const maxDim = Math.max(size.x, size.y, size.z, 0.05);
  const fov = (camera.fov * Math.PI) / 180;
  const dist = (maxDim / (2 * Math.tan(fov / 2))) * padding;
  camera.near = Math.max(dist / 200, 0.01);
  camera.far = Math.max(dist * 80, 400);
  camera.position.copy(center).add(new THREE.Vector3(dist * 0.7, dist * 0.55, dist * 0.7));
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.minDistance = Math.max(dist * 0.02, 0.02);
  controls.maxDistance = dist * 40;
  controls.update();
  return true;
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
