import type { Ray3 } from '@gs/viewer';
import { createRayFromNdc } from '@gs/viewer';
import type * as THREE from 'three';

export interface NdcPoint {
  x: number;
  y: number;
}

export function pointerToNdc(event: PointerEvent, canvas: HTMLCanvasElement): NdcPoint {
  const rect = canvas.getBoundingClientRect();
  const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  const y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  return { x, y };
}

export function rayFromPointer(
  event: PointerEvent,
  canvas: HTMLCanvasElement,
  camera: THREE.Camera,
): Ray3 {
  const ndc = pointerToNdc(event, canvas);
  return createRayFromNdc(ndc.x, ndc.y, camera);
}
