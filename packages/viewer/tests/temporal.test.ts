import { describe, expect, it } from 'vitest';

import { clusterOffsetAt, interpolateCamera } from '../src/temporal/cameras';

describe('câmeras temporais', () => {
  it('interpola pose entre dois frames COLMAP', () => {
    const cameras = [
      { t: 0, position: [0, 1, 4] as [number, number, number], target: [0, 1, 0] as [number, number, number] },
      { t: 1, position: [4, 1, 0] as [number, number, number], target: [0, 1, 0] as [number, number, number] },
    ];
    const mid = interpolateCamera(cameras, 0.5);
    expect(mid?.position[0]).toBeCloseTo(2);
    expect(mid?.position[2]).toBeCloseTo(2);
    expect(interpolateCamera(undefined, 0.5)).toBeNull();
  });

  it('média offsets dos clusters rígidos', () => {
    const offset = clusterOffsetAt(
      {
        enabled: true,
        frameCount: 2,
        durationS: 1,
        fps: 2,
        currentTime: 0.5,
        sourceKind: 'video',
        times: [0, 1],
        clusters: [
          { weight: 1, keys: [{ t: [0, 0, 0] }, { t: [2, 0, 0] }] },
        ],
      },
      0.5,
    );
    expect(offset[0]).toBeCloseTo(1);
  });
});
