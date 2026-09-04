import { describe, expect, it } from 'vitest';

import {
  compensatePoint,
  confidenceBand,
  hudCalibrationLabel,
  isCalibrated,
  metersFromScene,
  scaleFactorFromSceneAndMeters,
  shouldCompensateObjects,
  type CalibrationLike,
} from './scaleFactor';

const noneCal: CalibrationLike = { scaleFactor: null, source: 'none', confidence: null };
const autoCal: CalibrationLike = { scaleFactor: 0.85, source: 'auto-height', confidence: 0.9 };
const manualCal: CalibrationLike = { scaleFactor: 1.1, source: 'manual', confidence: null };

describe('scaleFactor', () => {
  it('calcula fator = metros / distância de cena', () => {
    expect(scaleFactorFromSceneAndMeters(2, 1.6)).toBeCloseTo(0.8, 12);
    expect(metersFromScene(2, 0.8)).toBeCloseTo(1.6, 12);
  });

  it('rejeita distâncias inválidas', () => {
    expect(() => scaleFactorFromSceneAndMeters(0, 1)).toThrow();
    expect(() => scaleFactorFromSceneAndMeters(1, 0)).toThrow();
  });

  it('compensa pontos ao redefinir o fator (mantém metros)', () => {
    const point = { x: 2, y: 0, z: 0 };
    const next = compensatePoint(point, 0.8, 1.6);
    expect(next.x).toBeCloseTo(1, 12);
    expect(metersFromScene(point.x, 0.8)).toBeCloseTo(metersFromScene(next.x, 1.6), 12);
  });

  it('só compensa objetos quando já havia calibração', () => {
    expect(shouldCompensateObjects(noneCal, autoCal)).toBe(false);
    expect(shouldCompensateObjects(autoCal, manualCal)).toBe(true);
    expect(shouldCompensateObjects(autoCal, autoCal)).toBe(false);
  });

  it('classifica confiança e monta o rótulo do HUD', () => {
    expect(confidenceBand(0.9)).toBe('alta');
    expect(confidenceBand(0.5)).toBe('media');
    expect(confidenceBand(0.1)).toBe('baixa');
    expect(isCalibrated(noneCal)).toBe(false);
    expect(hudCalibrationLabel(noneCal)).toBe('não calibrada');
    expect(hudCalibrationLabel(autoCal)).toBe('calibrada · auto-altura · conf. alta');
    expect(hudCalibrationLabel(manualCal)).toBe('calibrada · manual');
  });
});
