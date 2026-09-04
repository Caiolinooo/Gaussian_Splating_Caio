import { describe, expect, it } from 'vitest';

import { createUnitsBinding } from '../src/unitsBinding';

describe('viewer unitsBinding', () => {
  const port = createUnitsBinding();

  it('converts with decimal string output', () => {
    expect(port.convert(1, 'in', 'mm')).toBe('25.4');
    expect(port.convert('1.83', 'm', 'cm')).toBe('183');
  });

  it('formats pt-BR lengths', () => {
    expect(port.format(1.83, 'm', 'pt-BR')).toMatch(/1,83/);
  });
});
