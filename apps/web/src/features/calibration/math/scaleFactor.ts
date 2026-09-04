import type { ScenePoint } from './tapeMath';
import { distance3 } from './tapeMath';

export type CalibrationSource = 'auto-height' | 'manual' | 'none';

/** Subconjunto do `CalibrationJson` do SceneManager usado pela trena. */
export interface CalibrationLike {
  scaleFactor: number | null;
  source: CalibrationSource;
  confidence: number | null;
}

export type ConfidenceBand = 'alta' | 'media' | 'baixa' | 'desconhecida';

export function isFinitePositive(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0;
}

/** Cena está calibrada quando há fator > 0 e origem diferente de `none`. */
export function isCalibrated(calibration: CalibrationLike): boolean {
  return isFinitePositive(calibration.scaleFactor) && calibration.source !== 'none';
}

/**
 * `realMeters = sceneDistance * scaleFactor`.
 * `sceneDistance` é a distância no espaço local do nó-raiz (antes do scale).
 */
export function scaleFactorFromSceneAndMeters(sceneDistance: number, realMeters: number): number {
  if (!isFinitePositive(sceneDistance)) {
    throw new Error('A distância de cena precisa ser maior que zero.');
  }
  if (!isFinitePositive(realMeters)) {
    throw new Error('O comprimento real precisa ser maior que zero.');
  }
  return realMeters / sceneDistance;
}

export function metersFromScene(sceneDistance: number, scaleFactor: number): number {
  if (!Number.isFinite(sceneDistance) || !isFinitePositive(scaleFactor)) {
    return Number.NaN;
  }
  return sceneDistance * scaleFactor;
}

export function compensateComponent(value: number, oldFactor: number, newFactor: number): number {
  if (!isFinitePositive(oldFactor) || !isFinitePositive(newFactor)) {
    return value;
  }
  return value * (oldFactor / newFactor);
}

export function compensatePoint(
  point: ScenePoint,
  oldFactor: number,
  newFactor: number,
): ScenePoint {
  return {
    x: compensateComponent(point.x, oldFactor, newFactor),
    y: compensateComponent(point.y, oldFactor, newFactor),
    z: compensateComponent(point.z, oldFactor, newFactor),
  };
}

export function shouldCompensateObjects(previous: CalibrationLike, next: CalibrationLike): boolean {
  return (
    isCalibrated(previous) &&
    isCalibrated(next) &&
    previous.scaleFactor !== next.scaleFactor &&
    isFinitePositive(previous.scaleFactor) &&
    isFinitePositive(next.scaleFactor)
  );
}

export function confidenceBand(confidence: number | null | undefined): ConfidenceBand {
  if (confidence == null || !Number.isFinite(confidence)) {
    return 'desconhecida';
  }
  if (confidence >= 0.75) {
    return 'alta';
  }
  if (confidence >= 0.4) {
    return 'media';
  }
  return 'baixa';
}

export function sourceLabel(source: CalibrationSource): string {
  switch (source) {
    case 'auto-height':
      return 'auto-altura';
    case 'manual':
      return 'manual';
    case 'none':
      return 'não calibrada';
    default: {
      const exhaustive: never = source;
      return String(exhaustive);
    }
  }
}

/**
 * Texto persistente do HUD:
 * `calibrada · auto-altura · conf. alta` / `não calibrada`.
 */
export function hudCalibrationLabel(calibration: CalibrationLike): string {
  if (!isCalibrated(calibration)) {
    return 'não calibrada';
  }
  const parts = ['calibrada', sourceLabel(calibration.source)];
  if (calibration.source === 'auto-height') {
    const band = confidenceBand(calibration.confidence);
    if (band !== 'desconhecida') {
      parts.push(`conf. ${band}`);
    }
  }
  return parts.join(' · ');
}

export function suggestedReferencePoints(): { a: ScenePoint; b: ScenePoint } {
  return {
    a: { x: 0, y: 0, z: 0 },
    b: { x: 1, y: 0, z: 0 },
  };
}

export function suggestedSceneDistance(): number {
  const { a, b } = suggestedReferencePoints();
  return distance3(a, b);
}

export function rootScaleFromCalibration(calibration: CalibrationLike): number {
  return isCalibrated(calibration) && isFinitePositive(calibration.scaleFactor)
    ? calibration.scaleFactor
    : 1;
}
