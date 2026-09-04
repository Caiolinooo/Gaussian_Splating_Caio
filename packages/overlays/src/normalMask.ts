export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export interface NormalMaskParams {
  enabled: boolean;
  /** cos(ângulo máximo). Fragmento com facing < threshold é recusado. */
  threshold: number;
}

function hypot3(v: Vec3): number {
  return Math.hypot(v.x, v.y, v.z);
}

function normalize(v: Vec3): Vec3 {
  const len = hypot3(v);
  if (len === 0) {
    return { x: 0, y: 0, z: 0 };
  }
  return { x: v.x / len, y: v.y / len, z: v.z / len };
}

/**
 * Quanto a superfície aponta para o projetor: `N · (−D)`.
 * `projectorLookDir` é o eixo local −Z do projetor em espaço-mundo
 * (para onde a textura é “atirada”).
 *
 * - Parede de frente: N ≈ −D → facing ≈ 1.
 * - Quina 90°: N ⊥ D → facing ≈ 0 (sangramento cortado).
 */
export function surfaceFacing(worldNormal: Vec3, projectorLookDir: Vec3): number {
  const n = normalize(worldNormal);
  const d = normalize(projectorLookDir);
  return n.x * -d.x + n.y * -d.y + n.z * -d.z;
}

/**
 * `threshold = cos(maxAngle)`. Ângulo 60° → 0,5.
 */
export function thresholdFromMaxAngleRadians(maxAngle: number): number {
  if (!Number.isFinite(maxAngle) || maxAngle < 0 || maxAngle > Math.PI) {
    throw new Error(`maxAngle must be in [0, π], got ${String(maxAngle)}`);
  }
  return Math.cos(maxAngle);
}

/**
 * Aceita o fragmento se a máscara estiver desligada ou se facing ≥ threshold.
 * Igualdade no limiar passa (ângulo exatamente no máximo).
 */
export function passesNormalMask(facing: number, mask: NormalMaskParams): boolean {
  if (!mask.enabled) {
    return true;
  }
  return facing >= mask.threshold;
}

/** Combina facing + threshold num único predicado (espelha o `discard` do shader). */
export function shouldKeepFragment(
  worldNormal: Vec3,
  projectorLookDir: Vec3,
  mask: NormalMaskParams,
): boolean {
  if (!mask.enabled) {
    return true;
  }
  return passesNormalMask(surfaceFacing(worldNormal, projectorLookDir), mask);
}
