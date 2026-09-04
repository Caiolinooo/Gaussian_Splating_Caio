import { describe, expect, it } from 'vitest';

import {
  formatHeightMeters,
  heightInputToMeters,
  metersToApiField,
  parseLocaleNumber,
  validateHeightMeters,
} from '../height';

describe('parseLocaleNumber', () => {
  it('aceita vírgula pt-BR', () => {
    expect(parseLocaleNumber('1,75')).toBe(1.75);
  });

  it('aceita ponto', () => {
    expect(parseLocaleNumber('1.80')).toBe(1.8);
  });

  it('rejeita texto', () => {
    expect(parseLocaleNumber('alto')).toBeNull();
  });

  it('trata vazio como nulo', () => {
    expect(parseLocaleNumber('')).toBeNull();
  });
});

describe('heightInputToMeters', () => {
  it('converte 1,75 m', () => {
    const meters = heightInputToMeters({ system: 'metric', meters: '1,75', centimeters: '' });
    expect(meters).not.toBeNull();
    expect(meters!).toBeCloseTo(1.75, 6);
  });

  it('soma metros e centímetros via @gs/units', () => {
    const meters = heightInputToMeters({ system: 'metric', meters: '1', centimeters: '83' });
    expect(meters).toBeCloseTo(1.83, 6);
  });

  it('converte 5 ft 9 in', () => {
    const meters = heightInputToMeters({ system: 'imperial', feet: '5', inches: '9' });
    expect(meters).not.toBeNull();
    expect(meters!).toBeCloseTo(1.7526, 3);
  });

  it('devolve nulo sem valores', () => {
    expect(heightInputToMeters({ system: 'metric', meters: '', centimeters: '' })).toBeNull();
  });
});

describe('validateHeightMeters', () => {
  it('exige valor', () => {
    expect(validateHeightMeters(null)).toMatch(/informe/i);
  });

  it('rejeita fora da faixa do JobSpec (0,5–2,8 m)', () => {
    expect(validateHeightMeters(0.4)).toMatch(/entre/);
    expect(validateHeightMeters(3)).toMatch(/entre/);
  });

  it('aceita 1,75 m', () => {
    expect(validateHeightMeters(1.75)).toBeNull();
  });
});

describe('format e campo da API', () => {
  it('formata em pt-BR e imperial ao vivo', () => {
    expect(formatHeightMeters(1.83, 'metric')).toBe('1,83 m');
    expect(formatHeightMeters(1.6764, 'imperial')).toMatch(/5'/);
  });

  it('serializa user_height_m com ponto decimal', () => {
    expect(metersToApiField(1.75)).toBe('1.75');
    expect(metersToApiField(1.8)).toBe('1.8');
  });
});
