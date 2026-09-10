import { describe, expect, it } from 'vitest';
import * as THREE from 'three';

import { clampPitchAndLevel, FLY_PITCH_LIMIT, flySpeedsForBounds, pivotAhead } from './flyMath';

describe('flySpeedsForBounds', () => {
  it('escala com a diagonal da cena', () => {
    const small = flySpeedsForBounds(10);
    const big = flySpeedsForBounds(100);
    expect(big.move).toBeCloseTo(small.move * 10, 5);
    expect(big.scroll).toBeGreaterThan(small.scroll);
    expect(big.slide).toBeGreaterThan(small.slide);
  });

  it('move a 15% da diagonal por segundo', () => {
    const speeds = flySpeedsForBounds(70);
    expect(speeds.move).toBeCloseTo(70 * 0.15, 5);
    expect(70 / speeds.move).toBeCloseTo(1 / 0.15, 5);
  });

  it('satura em pisos e tetos', () => {
    expect(flySpeedsForBounds(0.001).move).toBeGreaterThanOrEqual(0.4);
    expect(flySpeedsForBounds(10_000).move).toBeLessThanOrEqual(40);
  });

  it('cai no default quando a diagonal é inválida', () => {
    expect(flySpeedsForBounds(Number.NaN)).toEqual(flySpeedsForBounds(10));
    expect(flySpeedsForBounds(-3)).toEqual(flySpeedsForBounds(10));
  });
});

describe('clampPitchAndLevel', () => {
  it('limita o pitch além de ±85° e zera o roll', () => {
    // 1.55 rad (88,8°) está acima do limite e ainda round-tripa em YXZ
    // (pitch > 90° é reembrulhado pela extração e nunca ocorre no voo —
    // o FpsMovement do Spark já clampeia em ±90°).
    const quaternion = new THREE.Quaternion().setFromEuler(new THREE.Euler(1.55, 0.4, 0.3, 'YXZ'));
    clampPitchAndLevel(quaternion);
    const euler = new THREE.Euler().setFromQuaternion(quaternion, 'YXZ');
    expect(euler.x).toBeCloseTo(FLY_PITCH_LIMIT, 5);
    expect(euler.y).toBeCloseTo(0.4, 5);
    expect(euler.z).toBeCloseTo(0, 5);
  });

  it('não altera orientação dentro da faixa', () => {
    const quaternion = new THREE.Quaternion().setFromEuler(new THREE.Euler(0.3, -0.8, 0, 'YXZ'));
    const before = quaternion.clone();
    clampPitchAndLevel(quaternion);
    expect(quaternion.angleTo(before)).toBeCloseTo(0, 6);
  });
});

describe('pivotAhead', () => {
  it('devolve o ponto à frente da câmera na distância pedida', () => {
    const position = new THREE.Vector3(1, 2, 3);
    const quaternion = new THREE.Quaternion().setFromEuler(new THREE.Euler(0, Math.PI / 2, 0, 'YXZ'));
    const pivot = pivotAhead(position, quaternion, 4);
    // Yaw de +90° gira o -Z da câmera para -X do mundo.
    expect(pivot.x).toBeCloseTo(1 - 4, 5);
    expect(pivot.y).toBeCloseTo(2, 5);
    expect(pivot.z).toBeCloseTo(3, 5);
  });

  it('reusa o vetor de resultado', () => {
    const result = new THREE.Vector3();
    const returned = pivotAhead(new THREE.Vector3(), new THREE.Quaternion(), 1, result);
    expect(returned).toBe(result);
    expect(result.z).toBeCloseTo(-1, 5);
  });
});
