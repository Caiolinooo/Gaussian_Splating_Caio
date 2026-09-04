import type { LengthUnit } from '@gs/viewer';

import { assertNever } from '../../viewer/assertNever';

export type UnitSystem = 'metric' | 'imperial';

export interface UnitPreference {
  system: UnitSystem;
  unit: LengthUnit;
}

export const UNIT_PREF_STORAGE_KEY = 'gs:unit-system';

const DEFAULT_PREF: UnitPreference = { system: 'metric', unit: 'm' };

function isLengthUnit(value: unknown): value is LengthUnit {
  switch (value) {
    case 'mm':
    case 'cm':
    case 'm':
    case 'in':
    case 'ft':
      return true;
    default:
      return false;
  }
}

function isUnitSystem(value: unknown): value is UnitSystem {
  switch (value) {
    case 'metric':
    case 'imperial':
      return true;
    default:
      return false;
  }
}

export function defaultUnitForSystem(system: UnitSystem): LengthUnit {
  switch (system) {
    case 'metric':
      return 'm';
    case 'imperial':
      return 'ft';
    default:
      return assertNever(system);
  }
}

export function unitsForSystem(system: UnitSystem): readonly LengthUnit[] {
  switch (system) {
    case 'metric':
      return ['mm', 'cm', 'm'];
    case 'imperial':
      return ['in', 'ft'];
    default:
      return assertNever(system);
  }
}

/** Snap de translação em metros reais (1 cm / 0,5 in). */
export function snapTranslateMeters(unit: LengthUnit): number {
  switch (unit) {
    case 'mm':
      return 0.001;
    case 'cm':
    case 'm':
      return 0.01;
    case 'in':
    case 'ft':
      return 0.5 * 0.0254;
    default:
      return assertNever(unit);
  }
}

export function loadUnitPreference(): UnitPreference {
  try {
    const raw = localStorage.getItem(UNIT_PREF_STORAGE_KEY);
    if (!raw) {
      return { ...DEFAULT_PREF };
    }
    const parsed: unknown = JSON.parse(raw);
    if (isUnitSystem(parsed)) {
      return { system: parsed, unit: defaultUnitForSystem(parsed) };
    }
    if (
      parsed !== null &&
      typeof parsed === 'object' &&
      isUnitSystem((parsed as { system?: unknown }).system) &&
      isLengthUnit((parsed as { unit?: unknown }).unit)
    ) {
      const system = (parsed as UnitPreference).system;
      const unit = (parsed as UnitPreference).unit;
      const allowed = unitsForSystem(system);
      return { system, unit: allowed.includes(unit) ? unit : defaultUnitForSystem(system) };
    }
  } catch {
    // quota / JSON inválido
  }
  return { ...DEFAULT_PREF };
}

export function persistUnitPreference(pref: UnitPreference): void {
  try {
    localStorage.setItem(UNIT_PREF_STORAGE_KEY, JSON.stringify(pref));
  } catch {
    // ignore
  }
}
