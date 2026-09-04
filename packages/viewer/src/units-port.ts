import { assertNever } from './assertNever';

/**
 * Unidades de comprimento suportadas pelo contrato local.
 * Espelha o núcleo `@gs/units` sem importá-lo (inversão de dependência).
 */
export type LengthUnit = 'mm' | 'cm' | 'm' | 'in' | 'ft';

export const LENGTH_UNITS: readonly LengthUnit[] = ['mm', 'cm', 'm', 'in', 'ft'];

/**
 * Porta de unidades injetável pelo app.
 * O app deve fazer o bind com `@gs/units` depois que a API daquele pacote estabilizar.
 */
export interface UnitsPort {
  /** Converte `value` de `from` para `to`. Retorna string decimal (sem float binário). */
  convert(value: number | string, from: LengthUnit, to: LengthUnit): string;
  /** Formata um comprimento para exibição (ex.: pt-BR "1,83 m"). */
  format(value: number | string, unit: LengthUnit, locale?: string): string;
}

const MM_PER_UNIT: Record<LengthUnit, number> = {
  mm: 1,
  cm: 10,
  m: 1000,
  in: 25.4,
  ft: 304.8,
};

/**
 * Implementação de fallback (float) para testes e boot sem `@gs/units`.
 * Não use em produção de medição — o app deve injetar o núcleo decimal.
 */
export function createFallbackUnitsPort(): UnitsPort {
  return {
    convert(value: number | string, from: LengthUnit, to: LengthUnit): string {
      assertUnit(from);
      assertUnit(to);
      const n = typeof value === 'number' ? value : Number(value);
      const mm = n * MM_PER_UNIT[from];
      return String(mm / MM_PER_UNIT[to]);
    },
    format(value: number | string, unit: LengthUnit, locale = 'pt-BR'): string {
      assertUnit(unit);
      const n = typeof value === 'number' ? value : Number(value);
      const formatted = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(n);
      switch (unit) {
        case 'mm':
        case 'cm':
        case 'm':
          return `${formatted} ${unit}`;
        case 'in':
          return `${formatted}"`;
        case 'ft':
          return `${formatted}'`;
        default:
          return assertNever(unit);
      }
    },
  };
}

function assertUnit(unit: LengthUnit): void {
  switch (unit) {
    case 'mm':
    case 'cm':
    case 'm':
    case 'in':
    case 'ft':
      return;
    default:
      assertNever(unit, `Unidade não suportada: ${String(unit)}`);
  }
}
