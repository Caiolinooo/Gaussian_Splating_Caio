import { describe, expect, it } from 'vitest';

import {
  createOverlayUnitsPort,
  createViewerUnitsPort,
  formatMeters,
  fromMeters,
  toMeters,
} from '../../../lib/unitsBinding';

describe('unitsBinding (núcleo @gs/units)', () => {
  it('converte metros ↔ cm', () => {
    expect(toMeters(183, 'cm')).toBeCloseTo(1.83, 10);
    expect(fromMeters(1.83, 'cm')).toBeCloseTo(183, 10);
  });

  it('formata pt-BR em metros', () => {
    expect(formatMeters(1.83, 'm')).toBe('1,83 m');
  });

  it('viewer port devolve string decimal', () => {
    const port = createViewerUnitsPort();
    expect(port.convert(1, 'in', 'mm')).toBe('25.4');
    expect(port.format(1.83, 'm')).toBe('1,83 m');
  });

  it('overlay port lê o fator da cena', () => {
    let factor = 0.5;
    const port = createOverlayUnitsPort(() => factor);
    expect(port.convert(10, 'cm', 'm')).toBeCloseTo(0.1, 10);
    expect(port.sceneMetersPerUnit()).toBe(0.5);
    factor = 0;
    expect(port.sceneMetersPerUnit()).toBe(1);
  });
});
