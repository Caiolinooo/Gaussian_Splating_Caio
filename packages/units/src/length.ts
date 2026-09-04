import Big from 'big.js';

/** Unidades suportadas pelo núcleo (SI + imperial). */
export const UNITS = ['mm', 'cm', 'm', 'in', 'ft'] as const;
export type Unit = (typeof UNITS)[number];

/** Fatores exatos: quantos milímetros há em cada unidade (base interna: mm). */
const MILLIMETERS_PER_UNIT: Record<Unit, string> = {
  mm: '1',
  cm: '10',
  m: '1000',
  in: '25.4',
  ft: '304.8',
};

/**
 * Comprimento com precisão decimal (`big.js`): valor + unidade de origem.
 * A conversão sempre passa pela base interna em milímetros.
 */
export interface Length {
  readonly value: Big;
  readonly unit: Unit;
}

/** Cria um comprimento. Aceita number/string/Big (string evita erro de ponto flutuante). */
export function length(value: number | string | Big, unit: Unit): Length {
  return { value: value instanceof Big ? value : new Big(value), unit };
}

/** Valor absoluto do comprimento na base interna (milímetros). */
export function toMillimeters(input: Length): Big {
  return input.value.times(MILLIMETERS_PER_UNIT[input.unit]);
}

/** Recria um comprimento a partir de milímetros, na unidade desejada. */
export function fromMillimeters(mm: Big, unit: Unit): Length {
  return { value: mm.div(MILLIMETERS_PER_UNIT[unit]), unit };
}

/** Converte `value` de uma unidade para outra, com precisão decimal. */
export function convert(value: number | string | Big, from: Unit, to: Unit): Big {
  return toMillimeters(length(value, from)).div(MILLIMETERS_PER_UNIT[to]);
}

/** Retorna o mesmo comprimento expresso em outra unidade. */
export function toUnit(input: Length, unit: Unit): Length {
  return fromMillimeters(toMillimeters(input), unit);
}
