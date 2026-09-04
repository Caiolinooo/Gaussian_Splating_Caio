/**
 * Autoverificação sem Vitest (roda com `node --experimental-strip-types`).
 * Espelha os casos de `tapeMath.test.ts` e `scaleFactor.test.ts`.
 */
import {
  compensatePoint,
  hudCalibrationLabel,
  isCalibrated,
  metersFromScene,
  scaleFactorFromSceneAndMeters,
  shouldCompensateObjects,
  type CalibrationLike,
} from './scaleFactor';
import { distance3, midpoint3 } from './tapeMath';

function assert(condition: boolean, message: string): void {
  if (!condition) {
    throw new Error(message);
  }
}

function close(actual: number, expected: number, digits = 10): boolean {
  return Math.abs(actual - expected) < 10 ** -digits;
}

export function runCalibrationSelfCheck(): void {
  assert(close(distance3({ x: 0, y: 0, z: 0 }, { x: 3, y: 4, z: 0 }), 5), '3-4-5');
  const mid = midpoint3({ x: 0, y: 0, z: 2 }, { x: 2, y: 4, z: 2 });
  assert(mid.x === 1 && mid.y === 2 && mid.z === 2, 'midpoint');

  assert(close(scaleFactorFromSceneAndMeters(2, 1.6), 0.8), 'scale factor');
  assert(close(metersFromScene(2, 0.8), 1.6), 'meters from scene');

  const compensated = compensatePoint({ x: 2, y: 0, z: 0 }, 0.8, 1.6);
  assert(close(compensated.x, 1), 'compensate x');

  const noneCal: CalibrationLike = { scaleFactor: null, source: 'none', confidence: null };
  const autoCal: CalibrationLike = { scaleFactor: 0.85, source: 'auto-height', confidence: 0.9 };
  const manualCal: CalibrationLike = { scaleFactor: 1.1, source: 'manual', confidence: null };
  assert(!isCalibrated(noneCal), 'none not calibrated');
  assert(shouldCompensateObjects(autoCal, manualCal), 'compensate on redefine');
  assert(!shouldCompensateObjects(noneCal, autoCal), 'no compensate on first apply');
  assert(hudCalibrationLabel(noneCal) === 'não calibrada', 'hud none');
  assert(hudCalibrationLabel(autoCal) === 'calibrada · auto-altura · conf. alta', 'hud auto');
  assert(hudCalibrationLabel(manualCal) === 'calibrada · manual', 'hud manual');
}

runCalibrationSelfCheck();
