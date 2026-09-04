/**
 * Bind de `@gs/units` para as portas locais de `@gs/viewer` e `@gs/overlays`.
 *
 * Os pacotes **não** importam o núcleo — o app injeta estas implementações.
 * Conversões usam `big.js` (base interna em mm). `sceneMetersPerUnit` lê o
 * `scaleFactor` da calibração (metros reais por unidade de cena no nó-raiz).
 */

import type { LengthUnit as OverlayLengthUnit, UnitsPort as OverlayUnitsPort } from '@gs/overlays';
import { convert, formatLength, length, type Unit } from '@gs/units';
import type { LengthUnit as ViewerLengthUnit, UnitsPort as ViewerUnitsPort } from '@gs/viewer';

export type AppLengthUnit = ViewerLengthUnit & OverlayLengthUnit;

function asUnit(unit: ViewerLengthUnit | OverlayLengthUnit): Unit {
  return unit;
}

/** Converte para metros (número IEEE só na borda da UI). */
export function toMeters(
  value: number | string,
  unit: ViewerLengthUnit | OverlayLengthUnit,
): number {
  return Number(convert(value, asUnit(unit), 'm').toString());
}

/** Converte metros para a unidade de exibição. */
export function fromMeters(
  meters: number | string,
  unit: ViewerLengthUnit | OverlayLengthUnit,
): number {
  return Number(convert(meters, 'm', asUnit(unit)).toString());
}

/** Formata um comprimento já expresso na unidade pedida (pt-BR). */
export function formatInUnit(
  value: number | string,
  unit: ViewerLengthUnit | OverlayLengthUnit,
  locale = 'pt-BR',
): string {
  const style = unit === 'ft' ? 'imperial' : 'unit';
  return formatLength(length(value, asUnit(unit)), { locale, style });
}

/** Formata metros na unidade ativa. */
export function formatMeters(
  meters: number,
  unit: ViewerLengthUnit | OverlayLengthUnit,
  locale = 'pt-BR',
): string {
  return formatInUnit(fromMeters(meters, unit), unit, locale);
}

/** Porta do viewer: `convert` devolve string decimal (sem float binário). */
export function createViewerUnitsPort(): ViewerUnitsPort {
  return {
    convert(value, from, to) {
      return convert(value, asUnit(from), asUnit(to)).toString();
    },
    format(value, unit, locale = 'pt-BR') {
      return formatInUnit(value, unit, locale);
    },
  };
}

/**
 * Porta de overlays: `convert` devolve number; `sceneMetersPerUnit` é o
 * fator do nó-raiz (`worldMeters = sceneUnits * factor`).
 */
export function createOverlayUnitsPort(getSceneMetersPerUnit: () => number): OverlayUnitsPort {
  return {
    convert(value, from, to) {
      return Number(convert(value, asUnit(from), asUnit(to)).toString());
    },
    format(value, unit, options) {
      const locale = options?.locale ?? 'pt-BR';
      const style = options?.style ?? (unit === 'ft' ? 'imperial' : 'unit');
      return formatLength(length(value, asUnit(unit)), { locale, style });
    },
    sceneMetersPerUnit() {
      const factor = getSceneMetersPerUnit();
      return Number.isFinite(factor) && factor > 0 ? factor : 1;
    },
  };
}
