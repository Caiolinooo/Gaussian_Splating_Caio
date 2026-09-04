import { describe, expect, it } from 'vitest';

import {
  passesNormalMask,
  shouldKeepFragment,
  surfaceFacing,
  thresholdFromMaxAngleRadians,
} from '../src/normalMask';

describe('máscara por normal (threshold)', () => {
  const lookIntoWall = { x: 0, y: 0, z: -1 };

  it('parede de frente: N = (0,0,1), look = (0,0,−1) → facing = 1', () => {
    expect(surfaceFacing({ x: 0, y: 0, z: 1 }, lookIntoWall)).toBeCloseTo(1, 12);
  });

  it('quina 90°: N = (1,0,0), look = (0,0,−1) → facing = 0', () => {
    expect(surfaceFacing({ x: 1, y: 0, z: 0 }, lookIntoWall)).toBeCloseTo(0, 12);
  });

  it('threshold de 60° é 0,5', () => {
    expect(thresholdFromMaxAngleRadians(Math.PI / 3)).toBeCloseTo(0.5, 12);
  });

  it('com threshold 0,5: 45° passa, 60° passa, 70° é recusado', () => {
    const mask = { enabled: true, threshold: 0.5 };
    const deg = (angle: number) => ({
      x: Math.sin(angle),
      y: 0,
      z: Math.cos(angle),
    });

    expect(shouldKeepFragment(deg(Math.PI / 4), lookIntoWall, mask)).toBe(true);
    expect(shouldKeepFragment(deg(Math.PI / 3), lookIntoWall, mask)).toBe(true);
    expect(shouldKeepFragment(deg((70 * Math.PI) / 180), lookIntoWall, mask)).toBe(false);

    expect(passesNormalMask(Math.cos(Math.PI / 4), mask)).toBe(true);
    expect(passesNormalMask(0.5, mask)).toBe(true);
    expect(passesNormalMask(Math.cos((70 * Math.PI) / 180), mask)).toBe(false);
  });

  it('máscara desligada aceita qualquer facing (inclusive quina)', () => {
    const mask = { enabled: false, threshold: 0.99 };
    expect(shouldKeepFragment({ x: 1, y: 0, z: 0 }, lookIntoWall, mask)).toBe(true);
    expect(passesNormalMask(-1, mask)).toBe(true);
  });

  it('normal nula produz facing 0', () => {
    expect(surfaceFacing({ x: 0, y: 0, z: 0 }, lookIntoWall)).toBe(0);
  });

  it('rejeita ângulo fora de [0, π]', () => {
    expect(() => thresholdFromMaxAngleRadians(-0.1)).toThrow(/maxAngle/);
    expect(() => thresholdFromMaxAngleRadians(4)).toThrow(/maxAngle/);
  });
});
