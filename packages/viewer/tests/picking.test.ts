import { describe, expect, it } from 'vitest';

import { pickClosestSplatCenter } from '../src/picking/splatCenters';

describe('picking aproximado por centro de gaussiana', () => {
  it('escolhe o centro mais próximo do raio', () => {
    const hit = pickClosestSplatCenter(
      { origin: { x: 0, y: 0, z: 0 }, direction: { x: 0, y: 0, z: -1 } },
      [
        { index: 0, center: { x: 10, y: 0, z: -5 }, handleId: 'far' },
        { index: 1, center: { x: 0.1, y: 0, z: -5 }, handleId: 'near' },
        { index: 2, center: { x: 0, y: 4, z: -2 }, handleId: 'up' },
      ],
    );
    expect(hit?.handleId).toBe('near');
    expect(hit?.index).toBe(1);
    expect(hit?.distance).toBeLessThan(0.2);
  });

  it('respeita maxDistance e minOpacity', () => {
    const hit = pickClosestSplatCenter(
      { origin: { x: 0, y: 0, z: 0 }, direction: { x: 1, y: 0, z: 0 } },
      [
        { index: 0, center: { x: 2, y: 3, z: 0 }, opacity: 0.9, handleId: 'too-far' },
        { index: 1, center: { x: 2, y: 0.05, z: 0 }, opacity: 0.01, handleId: 'transparent' },
        { index: 2, center: { x: 2, y: 0.2, z: 0 }, opacity: 0.5, handleId: 'ok' },
      ],
      { maxDistance: 0.5, minOpacity: 0.2 },
    );
    expect(hit?.handleId).toBe('ok');
  });

  it('retorna null sem candidatos', () => {
    const hit = pickClosestSplatCenter(
      { origin: { x: 0, y: 0, z: 0 }, direction: { x: 0, y: 1, z: 0 } },
      [{ index: 0, center: { x: 50, y: 0, z: 0 } }],
      { maxDistance: 1 },
    );
    expect(hit).toBeNull();
  });
});
