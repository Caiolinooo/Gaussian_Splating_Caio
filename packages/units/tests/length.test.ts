import { describe, expect, it } from 'vitest';

import {
  UNITS,
  convert,
  formatLength,
  fromMillimeters,
  length,
  toMillimeters,
  toUnit,
  type Unit,
} from '../src';

describe('conversões exatas (base interna em mm)', () => {
  it('converte valores conhecidos', () => {
    expect(convert(1, 'in', 'mm').toString()).toBe('25.4');
    expect(convert(1, 'ft', 'in').toString()).toBe('12');
    expect(convert(1.83, 'm', 'mm').toString()).toBe('1830');
    expect(convert(183, 'cm', 'm').toString()).toBe('1.83');
    expect(convert(10, 'mm', 'cm').toString()).toBe('1');
  });

  it.each(UNITS)('round-trip %s → mm → %s preserva o valor exato', (unit: Unit) => {
    const original = length('123.456', unit);
    const roundTripped = fromMillimeters(toMillimeters(original), unit);
    expect(roundTripped.value.toString()).toBe(original.value.toString());
  });

  it.each(UNITS)('round-trip cruzado a partir de %s com erro < 1e-9', (from: Unit) => {
    const original = length('7.25', from);
    for (const to of UNITS) {
      const back = toUnit(toUnit(original, to), from);
      const delta = Number(back.value.minus(original.value).abs().toString());
      expect(delta).toBeLessThan(1e-9);
    }
  });
});

describe('formatação', () => {
  it('formata metros em pt-BR: "1,83 m"', () => {
    expect(formatLength(length(1.83, 'm'))).toBe('1,83 m');
  });

  it('formata milímetros sem casas decimais desnecessárias', () => {
    expect(formatLength(length(25, 'mm'))).toBe('25 mm');
  });

  it('formata centímetros com vírgula decimal', () => {
    expect(formatLength(length(12.5, 'cm'))).toBe('12,5 cm');
  });

  it('formata polegadas com símbolo colado', () => {
    expect(formatLength(length(6, 'in'))).toBe('6"');
  });

  it('formata no estilo imperial: 5\' 6"', () => {
    expect(formatLength(length(1676.4, 'mm'), { style: 'imperial' })).toBe(`5' 6"`);
  });

  it('estilo imperial carrega o arredondamento das polegadas para os pés', () => {
    // 12 polegadas exatas → 1' 0"
    expect(formatLength(length(304.8, 'mm'), { style: 'imperial' })).toBe(`1' 0"`);
  });
});
