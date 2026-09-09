import { describe, expect, it } from 'vitest';

import { evaluateShRgb, lightDirection, relightRgb } from '../src/relight/shEnv';

describe('SH-env relight', () => {
  it('muda RGB quando azimute/elevação mudam', () => {
    const a = evaluateShRgb(lightDirection(45, 35), 1);
    const b = evaluateShRgb(lightDirection(220, 10), 1.4);
    expect(a[0]).not.toBeCloseTo(b[0], 3);
    expect(relightRgb({ enabled: false, azimuthDeg: 45, elevationDeg: 35, intensity: 1 })).toEqual([
      1, 1, 1,
    ]);
    const on = relightRgb({ enabled: true, azimuthDeg: 45, elevationDeg: 35, intensity: 1 });
    expect(on[0]).toBeGreaterThan(0.2);
  });
});
