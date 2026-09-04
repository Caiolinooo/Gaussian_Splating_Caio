import Big from 'big.js';

import { toMillimeters, type Length, type Unit } from './length';

export interface FormatLengthOptions {
  /** Locale BCP 47 (padrão: pt-BR). */
  locale?: string;
  /** Máximo de casas decimais no estilo "unit" (padrão: 2). */
  maxFractionDigits?: number;
  /**
   * "unit": valor na unidade do comprimento (ex.: "1,83 m", '25 mm', 6").
   * "imperial": decomposição em pés + polegadas (ex.: 5' 6").
   */
  style?: 'unit' | 'imperial';
}

const INCHES_PER_FOOT = new Big(12);
const MILLIMETERS_PER_INCH = new Big('25.4');

/** Formata um comprimento para exibição, por padrão em pt-BR. */
export function formatLength(input: Length, options: FormatLengthOptions = {}): string {
  const style = options.style ?? 'unit';
  if (style === 'imperial') {
    return formatImperial(input, options);
  }
  const label = labelFor(input.unit);
  const number = new Intl.NumberFormat(options.locale ?? 'pt-BR', {
    maximumFractionDigits: options.maxFractionDigits ?? 2,
  }).format(Number(input.value.toString()));
  // Unidades com símbolo (′/″) colam no número; unidades SI levam espaço.
  return input.unit === 'in' || input.unit === 'ft' ? `${number}${label}` : `${number} ${label}`;
}

/** Símbolo/rótulo de cada unidade. */
function labelFor(unit: Unit): string {
  switch (unit) {
    case 'mm':
      return 'mm';
    case 'cm':
      return 'cm';
    case 'm':
      return 'm';
    case 'in':
      return '"';
    case 'ft':
      return "'";
    default: {
      const exhaustive: never = unit;
      throw new Error(`Unidade não suportada: ${String(exhaustive)}`);
    }
  }
}

/** Formata como pés + polegadas: 1676,4 mm → 5' 6". */
function formatImperial(input: Length, options: FormatLengthOptions): string {
  const totalInches = toMillimeters(input).div(MILLIMETERS_PER_INCH);
  let feet = totalInches.div(INCHES_PER_FOOT).round(0, Big.roundDown);
  let inches = totalInches.minus(feet.times(INCHES_PER_FOOT)).round(1, Big.roundHalfUp);
  // Arredondamento pode "estourar" as polegadas (ex.: 11,96" → 12") — carrega para os pés.
  if (inches.gte(INCHES_PER_FOOT)) {
    feet = feet.plus(1);
    inches = inches.minus(INCHES_PER_FOOT);
  }
  const inchesNumber = new Intl.NumberFormat(options.locale ?? 'pt-BR', {
    maximumFractionDigits: 1,
  }).format(Number(inches.toString()));
  return `${feet.toString()}' ${inchesNumber}"`;
}
