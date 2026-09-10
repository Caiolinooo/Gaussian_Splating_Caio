import * as THREE from 'three';

/**
 * Pitch máximo no modo voar. Além disso, realinhar a órbita com
 * up (0,1,0) degenera (lookAt com direção ≈ up).
 */
export const FLY_PITCH_LIMIT = THREE.MathUtils.degToRad(85);

export interface FlySpeeds {
  /** Unidades por segundo no WASD/setas sem modificadores. */
  move: number;
  /** Unidades por pixel de arraste (slide com botão do meio/direito). */
  slide: number;
  /** Unidades por clique de roda. */
  scroll: number;
}

/**
 * Velocidades derivadas do tamanho da cena: sem Shift, atravessar a
 * diagonal leva ~6,7s (Shift ×5, Ctrl ×1/5); a roda anda ~0,2% da
 * diagonal por clique. Cena sem bounds cai no default de 10 unidades.
 */
export function flySpeedsForBounds(diagonal: number): FlySpeeds {
  const safe = Number.isFinite(diagonal) && diagonal > 0 ? diagonal : 10;
  return {
    move: THREE.MathUtils.clamp(safe * 0.15, 0.4, 40),
    slide: THREE.MathUtils.clamp(safe * 0.004, 0.01, 1.5),
    scroll: THREE.MathUtils.clamp(safe * 0.002, 0.005, 0.8),
  };
}

/**
 * Limita o pitch e zera o roll preservando o yaw — a ponte entre o modo
 * voar (câmera livre) e a órbita, que assume up (0,1,0). Mutate in place.
 */
export function clampPitchAndLevel(
  quaternion: THREE.Quaternion,
  limit: number = FLY_PITCH_LIMIT,
): THREE.Quaternion {
  const euler = new THREE.Euler().setFromQuaternion(quaternion, 'YXZ');
  euler.x = THREE.MathUtils.clamp(euler.x, -limit, limit);
  euler.z = 0;
  return quaternion.setFromEuler(euler);
}

/**
 * Ponto à frente da câmera na `distance` — onde o pivô da órbita deve
 * ficar para o OrbitControls continuar coerente após voar.
 */
export function pivotAhead(
  position: THREE.Vector3,
  quaternion: THREE.Quaternion,
  distance: number,
  result = new THREE.Vector3(),
): THREE.Vector3 {
  return result.set(0, 0, -1).applyQuaternion(quaternion).multiplyScalar(distance).add(position);
}
