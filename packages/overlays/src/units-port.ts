import { isLengthUnit, type LengthUnit } from './types';

/**
 * Porta local de unidades (inversão de dependência).
 *
 * Este pacote **não** importa `@gs/units` — outro agente é dono daquele
 * workspace. O app faz o bind depois, por exemplo:
 *
 * ```ts
 * import { convert, formatLength, length } from '@gs/units';
 *
 * const unitsPort: UnitsPort = {
 *   convert: (value, from, to) => Number(convert(value, from, to).toString()),
 *   format: (value, unit, options) => formatLength(length(value, unit), options),
 *   sceneMetersPerUnit: () => calibration.metersPerSceneUnit,
 * };
 * ```
 *
 * Convenção de escala: `worldMeters = sceneUnits * sceneMetersPerUnit()`.
 * É o fator aplicado ao nó-raiz calibrado do viewer (Fase 4).
 */
export interface UnitsPort {
  /** Converte um valor entre unidades SI/imperial. */
  convert(value: number | string, from: LengthUnit, to: LengthUnit): number;
  /** Formata um comprimento para exibição (pt-BR por padrão no bind). */
  format(
    value: number | string,
    unit: LengthUnit,
    options?: { locale?: string; style?: 'unit' | 'imperial' },
  ): string;
  /**
   * Metros reais por unidade de cena.
   * Sem calibração, o app deve devolver `1` (1 unidade = 1 m) ou recusar overlays.
   */
  sceneMetersPerUnit(): number;
}

/** Fatores exatos: milímetros por unidade (espelha `@gs/units`, sem importá-lo). */
const MILLIMETERS_PER_UNIT: Record<LengthUnit, number> = {
  mm: 1,
  cm: 10,
  m: 1000,
  in: 25.4,
  ft: 304.8,
};

/**
 * Porta de fallback para testes e preview antes do bind de `@gs/units`.
 * Usa aritmética IEEE-754 (suficiente para tiling; o núcleo de unidades
 * usa `big.js` para a trena).
 */
export function createFallbackUnitsPort(sceneMetersPerUnit = 1): UnitsPort {
  return {
    convert(value, from, to) {
      if (!isLengthUnit(from) || !isLengthUnit(to)) {
        throw new Error(`Unsupported unit: ${String(from)} → ${String(to)}`);
      }
      const numeric = typeof value === 'number' ? value : Number(value);
      if (!Number.isFinite(numeric)) {
        throw new Error(`Non-finite length value: ${String(value)}`);
      }
      const mm = numeric * MILLIMETERS_PER_UNIT[from];
      return mm / MILLIMETERS_PER_UNIT[to];
    },
    format(value, unit, options) {
      const numeric = typeof value === 'number' ? value : Number(value);
      const locale = options?.locale ?? 'pt-BR';
      const formatted = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(numeric);
      return unit === 'in' || unit === 'ft'
        ? `${formatted}${unit === 'in' ? '"' : "'"}`
        : `${formatted} ${unit}`;
    },
    sceneMetersPerUnit() {
      return sceneMetersPerUnit;
    },
  };
}
