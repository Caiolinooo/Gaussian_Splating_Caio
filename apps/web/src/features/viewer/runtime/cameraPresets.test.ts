import { describe, expect, it } from 'vitest';
import * as THREE from 'three';

import { fitOrbitToBox, poseForPreset } from './cameraPresets';

describe('cameraPresets', () => {
  it('presets orbitam o alvo informado', () => {
    const target = new THREE.Vector3(10, 2, -4);
    const iso = poseForPreset('iso', 8, target);
    expect(iso.target.x).toBeCloseTo(10);
    expect(iso.position.distanceTo(target)).toBeGreaterThan(4);
  });

  it('enquadra a caixa e move o alvo para o centro', () => {
    const camera = new THREE.PerspectiveCamera(50, 1, 0.05, 40);
    const controls = {
      target: new THREE.Vector3(0, 1, 0),
      minDistance: 0,
      maxDistance: 10,
      update() {
        return true;
      },
    };
    const ok = fitOrbitToBox(camera, controls as never, {
      min: { x: -20, y: 0, z: -20 },
      max: { x: 20, y: 8, z: 20 },
    });
    expect(ok).toBe(true);
    expect(controls.target.x).toBeCloseTo(0);
    expect(controls.target.y).toBeCloseTo(4);
    expect(camera.position.distanceTo(controls.target)).toBeGreaterThan(10);
    expect(camera.far).toBeGreaterThan(40);
  });
});
