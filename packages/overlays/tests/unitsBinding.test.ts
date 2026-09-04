import { describe, expect, it } from 'vitest';

import { createUnitsBinding } from '../src/unitsBinding';

describe('overlays unitsBinding', () => {
  const port = createUnitsBinding(() => 0.75);

  it('converts to a finite number', () => {
    expect(port.convert(10, 'cm', 'm')).toBeCloseTo(0.1, 12);
    expect(port.convert(1, 'in', 'mm')).toBeCloseTo(25.4, 12);
  });

  it('exposes sceneMetersPerUnit from the injector', () => {
    expect(port.sceneMetersPerUnit()).toBe(0.75);
  });

  it('falls back to 1 when the injector is invalid', () => {
    const fallback = createUnitsBinding(() => Number.NaN);
    expect(fallback.sceneMetersPerUnit()).toBe(1);
  });

  it('formats with locale options', () => {
    expect(port.format(1.83, 'm', { locale: 'pt-BR' })).toMatch(/1,83/);
  });
});
