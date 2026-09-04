import { DEFAULT_CALIBRATION, type CalibrationJson, type LengthUnit } from '@gs/viewer';
import { create } from 'zustand';

import type { CalibrationExtras } from '../../../lib/viewerApi';

import {
  defaultUnitForSystem,
  loadUnitPreference,
  persistUnitPreference,
  unitsForSystem,
  type UnitPreference,
  type UnitSystem,
} from './unitsPreference';

export type GatePhase = 'hidden' | 'auto-confirm' | 'blocked' | 'adjust';

export interface CalibrationStore {
  calibration: CalibrationJson;
  extras: CalibrationExtras;
  gatePhase: GatePhase;
  unitPref: UnitPreference;
  confirmedSceneId: string | null;
  setCalibration: (calibration: CalibrationJson, extras?: CalibrationExtras) => void;
  setExtras: (extras: CalibrationExtras) => void;
  setGatePhase: (phase: GatePhase) => void;
  setUnitSystem: (system: UnitSystem) => void;
  setLengthUnit: (unit: LengthUnit) => void;
  markConfirmed: (sceneId: string) => void;
}

function gateSeenKey(sceneId: string): string {
  return `gs:calibration-gate:${sceneId}`;
}

export function wasGateConfirmed(sceneId: string): boolean {
  try {
    return localStorage.getItem(gateSeenKey(sceneId)) === '1';
  } catch {
    return false;
  }
}

export function persistGateConfirmed(sceneId: string): void {
  try {
    localStorage.setItem(gateSeenKey(sceneId), '1');
  } catch {
    // ignore
  }
}

export const useCalibrationStore = create<CalibrationStore>((set) => ({
  calibration: { ...DEFAULT_CALIBRATION },
  extras: {},
  gatePhase: 'hidden',
  unitPref: loadUnitPreference(),
  confirmedSceneId: null,

  setCalibration(calibration, extras) {
    set((state) => ({
      calibration,
      extras: extras ?? state.extras,
    }));
  },
  setExtras(extras) {
    set({ extras });
  },
  setGatePhase(phase) {
    set({ gatePhase: phase });
  },
  setUnitSystem(system) {
    set((state) => {
      const allowed = unitsForSystem(system);
      const unit = allowed.includes(state.unitPref.unit)
        ? state.unitPref.unit
        : defaultUnitForSystem(system);
      const next: UnitPreference = { system, unit };
      persistUnitPreference(next);
      return { unitPref: next };
    });
  },
  setLengthUnit(unit) {
    set((state) => {
      const next: UnitPreference = { ...state.unitPref, unit };
      persistUnitPreference(next);
      return { unitPref: next };
    });
  },
  markConfirmed(sceneId) {
    persistGateConfirmed(sceneId);
    set({ confirmedSceneId: sceneId, gatePhase: 'hidden' });
  },
}));
