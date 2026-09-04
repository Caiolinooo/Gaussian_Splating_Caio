import { convert, formatLength, length } from '@gs/units';

import { HEIGHT_MAX_M, HEIGHT_MIN_M } from './constants';
import type { HeightSystem } from './types';

export interface MetricHeightInput {
  system: 'metric';
  meters: string;
  centimeters: string;
}

export interface ImperialHeightInput {
  system: 'imperial';
  feet: string;
  inches: string;
}

export type HeightInput = MetricHeightInput | ImperialHeightInput;

export function parseLocaleNumber(raw: string): number | null {
  const trimmed = raw.trim().replace(/\s/g, '').replace(',', '.');
  if (trimmed.length === 0) {
    return null;
  }
  if (!/^-?\d+(\.\d+)?$/.test(trimmed)) {
    return null;
  }
  const value = Number(trimmed);
  return Number.isFinite(value) ? value : null;
}

function isBlank(raw: string): boolean {
  return raw.trim().length === 0;
}

export function heightInputToMeters(input: HeightInput): number | null {
  switch (input.system) {
    case 'metric': {
      if (isBlank(input.meters) && isBlank(input.centimeters)) {
        return null;
      }
      const meters = parseLocaleNumber(input.meters) ?? 0;
      const centimeters = parseLocaleNumber(input.centimeters) ?? 0;
      if (input.meters.trim() !== '' && parseLocaleNumber(input.meters) === null) {
        return null;
      }
      if (input.centimeters.trim() !== '' && parseLocaleNumber(input.centimeters) === null) {
        return null;
      }
      const fromM = Number(convert(meters, 'm', 'm').toString());
      const fromCm = Number(convert(centimeters, 'cm', 'm').toString());
      return fromM + fromCm;
    }
    case 'imperial': {
      if (isBlank(input.feet) && isBlank(input.inches)) {
        return null;
      }
      const feet = parseLocaleNumber(input.feet) ?? 0;
      const inches = parseLocaleNumber(input.inches) ?? 0;
      if (input.feet.trim() !== '' && parseLocaleNumber(input.feet) === null) {
        return null;
      }
      if (input.inches.trim() !== '' && parseLocaleNumber(input.inches) === null) {
        return null;
      }
      const fromFt = Number(convert(feet, 'ft', 'm').toString());
      const fromIn = Number(convert(inches, 'in', 'm').toString());
      return fromFt + fromIn;
    }
    default: {
      const exhaustive: never = input;
      throw new Error(`Sistema de altura não tratado: ${String(exhaustive)}`);
    }
  }
}

export function validateHeightMeters(meters: number | null): string | null {
  if (meters === null) {
    return 'Informe a sua altura — ela calibra a escala real da cena.';
  }
  if (!Number.isFinite(meters)) {
    return 'Altura inválida. Use números (ex.: 1,75 m).';
  }
  if (meters < HEIGHT_MIN_M || meters > HEIGHT_MAX_M) {
    return `A altura deve estar entre ${HEIGHT_MIN_M.toLocaleString('pt-BR')} m e ${HEIGHT_MAX_M.toLocaleString('pt-BR')} m.`;
  }
  return null;
}

export function formatHeightMeters(meters: number, system: HeightSystem): string {
  switch (system) {
    case 'metric':
      return formatLength(length(meters, 'm'), { locale: 'pt-BR', maxFractionDigits: 2 });
    case 'imperial':
      return formatLength(length(meters, 'm'), { locale: 'pt-BR', style: 'imperial' });
    default: {
      const exhaustive: never = system;
      throw new Error(`Sistema de altura não tratado: ${String(exhaustive)}`);
    }
  }
}

/** Campo `user_height_m` da API: decimal com ponto, até 4 casas. */
export function metersToApiField(meters: number): string {
  const normalized = Number(convert(meters, 'm', 'm').toString());
  return normalized.toFixed(4).replace(/\.?0+$/, '');
}
