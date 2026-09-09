/** SH-env relight — mesmo modelo de `pipeline/relight/sh_env.py`. */

export interface RelightParams {
  enabled: boolean;
  azimuthDeg: number;
  elevationDeg: number;
  intensity: number;
}

export const DEFAULT_RELIGHT_PARAMS: RelightParams = Object.freeze({
  enabled: true,
  azimuthDeg: 45,
  elevationDeg: 35,
  intensity: 1,
});

export function lightDirection(
  azimuthDeg: number,
  elevationDeg: number,
): [number, number, number] {
  const az = (azimuthDeg * Math.PI) / 180;
  const el = (elevationDeg * Math.PI) / 180;
  const x = Math.cos(el) * Math.sin(az);
  const y = Math.sin(el);
  const z = Math.cos(el) * Math.cos(az);
  const length = Math.hypot(x, y, z) || 1;
  return [x / length, y / length, z / length];
}

export function evaluateShRgb(
  direction: [number, number, number],
  intensity: number,
  base: [number, number, number] = [0.72, 0.7, 0.66],
): [number, number, number] {
  const [nx, ny, nz] = direction;
  const lambert = Math.max(0, nx * 0.35 + ny * 0.85 + nz * 0.35);
  const ambient = 0.35;
  const scale = ambient + intensity * 0.85 * lambert;
  return [
    Math.min(1.8, base[0] * scale * (1 + 0.12 * Math.max(0, nx))),
    Math.min(1.8, base[1] * scale),
    Math.min(1.8, base[2] * scale * (1 + 0.08 * Math.max(0, -nx))),
  ];
}

export function relightRgb(params: RelightParams): [number, number, number] {
  if (!params.enabled) {
    return [1, 1, 1];
  }
  return evaluateShRgb(lightDirection(params.azimuthDeg, params.elevationDeg), params.intensity);
}
