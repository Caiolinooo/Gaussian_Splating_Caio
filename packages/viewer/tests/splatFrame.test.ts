import { describe, expect, it } from 'vitest';

import { IDENTITY_TRS } from '../src/math/trs';
import {
  createOpenCvToThreeTRS,
  isIdentityQuat,
  OPENCV_TO_THREE_QUAT,
} from '../src/renderer/splatFrame';
import { DEFAULT_SPLAT_QUALITY } from '../src/renderer/SplatRenderer';

describe('splatFrame', () => {
  it('marca identidade e aplica 180° em X (OpenCV → Y-up)', () => {
    expect(isIdentityQuat(IDENTITY_TRS.rotation)).toBe(true);
    expect(isIdentityQuat(OPENCV_TO_THREE_QUAT)).toBe(false);
    const trs = createOpenCvToThreeTRS();
    expect(trs.rotation).toEqual({ x: 1, y: 0, z: 0, w: 0 });
    expect(trs.scale).toEqual({ x: 1, y: 1, z: 1 });
  });
});

describe('DEFAULT_SPLAT_QUALITY', () => {
  it('abre com SH 3 (mesmo grau do treino gsplat)', () => {
    expect(DEFAULT_SPLAT_QUALITY.shDegree).toBe(3);
  });
});
