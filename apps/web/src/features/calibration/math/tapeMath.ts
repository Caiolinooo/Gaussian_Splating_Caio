/** Ponto 3D em espaço local do nó-raiz (unidades de cena). */
export interface ScenePoint {
  x: number;
  y: number;
  z: number;
}

export function distance3(a: ScenePoint, b: ScenePoint): number {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  const dz = a.z - b.z;
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

export function midpoint3(a: ScenePoint, b: ScenePoint): ScenePoint {
  return {
    x: (a.x + b.x) / 2,
    y: (a.y + b.y) / 2,
    z: (a.z + b.z) / 2,
  };
}

export function clonePoint(point: ScenePoint): ScenePoint {
  return { x: point.x, y: point.y, z: point.z };
}

export function pointsEqual(a: ScenePoint, b: ScenePoint, epsilon = 1e-8): boolean {
  return (
    Math.abs(a.x - b.x) <= epsilon &&
    Math.abs(a.y - b.y) <= epsilon &&
    Math.abs(a.z - b.z) <= epsilon
  );
}
