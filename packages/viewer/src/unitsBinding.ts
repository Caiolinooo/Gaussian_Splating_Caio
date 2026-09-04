import { convert, formatLength, length, type Unit } from '@gs/units';

import type { LengthUnit, UnitsPort } from './units-port';

function asUnit(unit: LengthUnit): Unit {
  return unit;
}

/**
 * Bind of `@gs/units` to the viewer `UnitsPort`.
 * `convert` returns a decimal string (no binary float).
 */
export function createUnitsBinding(): UnitsPort {
  return {
    convert(value, from, to) {
      return convert(value, asUnit(from), asUnit(to)).toString();
    },
    format(value, unit, locale = 'pt-BR') {
      const style = unit === 'ft' ? 'imperial' : 'unit';
      return formatLength(length(value, asUnit(unit)), { locale, style });
    },
  };
}
