import { convert, formatLength, length, type Unit } from '@gs/units';

import type { LengthUnit } from './types';
import type { UnitsPort } from './units-port';

function asUnit(unit: LengthUnit): Unit {
  return unit;
}

/**
 * Bind of `@gs/units` to the overlays `UnitsPort`.
 * `convert` returns a number; `sceneMetersPerUnit` is injected by the app.
 */
export function createUnitsBinding(getSceneMetersPerUnit: () => number): UnitsPort {
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
