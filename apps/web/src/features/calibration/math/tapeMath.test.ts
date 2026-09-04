import { describe, expect, it } from 'vitest';

import { clonePoint, distance3, midpoint3, pointsEqual } from './tapeMath';

describe('tapeMath', () => {
  it('mede o triângulo 3-4-5', () => {
    expect(distance3({ x: 0, y: 0, z: 0 }, { x: 3, y: 4, z: 0 })).toBeCloseTo(5, 12);
  });

  it('calcula o ponto médio', () => {
    expect(midpoint3({ x: 0, y: 0, z: 2 }, { x: 2, y: 4, z: 2 })).toEqual({ x: 1, y: 2, z: 2 });
  });

  it('clona sem alias', () => {
    const original = { x: 1, y: 2, z: 3 };
    const copy = clonePoint(original);
    copy.x = 9;
    expect(original.x).toBe(1);
    expect(pointsEqual(original, { x: 1, y: 2, z: 3 })).toBe(true);
  });
});
