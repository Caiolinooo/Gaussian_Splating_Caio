import type { TemporalCameraJson, TemporalJson } from '../editing/sceneSchema';

export interface TemporalPose {
  t: number;
  position: [number, number, number];
  target: [number, number, number];
  name?: string;
}

function lerp3(a: readonly number[], b: readonly number[], alpha: number): [number, number, number] {
  return [
    Number(a[0]) * (1 - alpha) + Number(b[0]) * alpha,
    Number(a[1]) * (1 - alpha) + Number(b[1]) * alpha,
    Number(a[2]) * (1 - alpha) + Number(b[2]) * alpha,
  ];
}

export function interpolateCamera(
  cameras: TemporalCameraJson[] | undefined,
  t: number,
): TemporalPose | null {
  if (!cameras || cameras.length === 0) {
    return null;
  }
  const first = cameras[0];
  const last = cameras[cameras.length - 1];
  if (!first || !last) {
    return null;
  }
  if (t <= first.t) {
    return { ...first, position: [...first.position], target: [...first.target] };
  }
  if (t >= last.t) {
    return { ...last, position: [...last.position], target: [...last.target] };
  }
  for (let index = 0; index < cameras.length - 1; index += 1) {
    const a = cameras[index];
    const b = cameras[index + 1];
    if (!a || !b) {
      continue;
    }
    if (a.t <= t && t <= b.t) {
      const span = b.t - a.t || 1;
      const alpha = (t - a.t) / span;
      return {
        t,
        position: lerp3(a.position, b.position, alpha),
        target: lerp3(a.target, b.target, alpha),
        name: a.name,
      };
    }
  }
  return { ...last, position: [...last.position], target: [...last.target] };
}

export function interpolateOffsets(
  times: number[] | undefined,
  keys: Array<{ t?: number[] }> | undefined,
  t: number,
): [number, number, number] {
  if (!times?.length || !keys?.length) {
    return [0, 0, 0];
  }
  const firstKey = keys[0]?.t ?? [0, 0, 0];
  const lastKey = keys[keys.length - 1]?.t ?? [0, 0, 0];
  if (t <= times[0]!) {
    return [Number(firstKey[0]), Number(firstKey[1]), Number(firstKey[2])];
  }
  if (t >= times[times.length - 1]!) {
    return [Number(lastKey[0]), Number(lastKey[1]), Number(lastKey[2])];
  }
  for (let index = 0; index < times.length - 1; index += 1) {
    const t0 = times[index]!;
    const t1 = times[index + 1]!;
    if (t0 <= t && t <= t1) {
      const span = t1 - t0 || 1;
      const alpha = (t - t0) / span;
      const a = keys[index]?.t ?? [0, 0, 0];
      const b = keys[index + 1]?.t ?? [0, 0, 0];
      return lerp3(a, b, alpha);
    }
  }
  return [Number(lastKey[0]), Number(lastKey[1]), Number(lastKey[2])];
}

export function clusterOffsetAt(temporal: TemporalJson, t: number): [number, number, number] {
  const clusters = temporal.clusters ?? [];
  let x = 0;
  let y = 0;
  let z = 0;
  let weight = 0;
  for (const cluster of clusters) {
    const keys = Array.isArray(cluster.keys) ? (cluster.keys as Array<{ t?: number[] }>) : [];
    const w = typeof cluster.weight === 'number' ? cluster.weight : 1;
    const offset = interpolateOffsets(temporal.times, keys, t);
    x += offset[0] * w;
    y += offset[1] * w;
    z += offset[2] * w;
    weight += w;
  }
  if (weight <= 0) {
    return [0, 0, 0];
  }
  return [x / weight, y / weight, z / weight];
}
