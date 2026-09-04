import { describe, expect, it } from 'vitest';

import {
  computePhysicalRepeat,
  lengthToMeters,
  physicalSizeToSceneExtents,
  resolveProjectorSizeScene,
  resolveTiling,
  sceneExtentToMeters,
} from '../src/physicalTiling';
import { createOverlay } from '../src/validate';
import { createFallbackUnitsPort } from '../src/units-port';

describe('lengthToMeters', () => {
  it('converte unidades conhecidas para metros', () => {
    expect(lengthToMeters({ value: 10, unit: 'cm' })).toBeCloseTo(0.1, 12);
    expect(lengthToMeters({ value: 100, unit: 'mm' })).toBeCloseTo(0.1, 12);
    expect(lengthToMeters({ value: 1, unit: 'm' })).toBe(1);
    expect(lengthToMeters({ value: 1, unit: 'in' })).toBeCloseTo(0.0254, 12);
    expect(lengthToMeters({ value: 1, unit: 'ft' })).toBeCloseTo(0.3048, 12);
  });

  it('usa UnitsPort.convert quando fornecido', () => {
    const units = createFallbackUnitsPort(1);
    expect(lengthToMeters({ value: 30, unit: 'cm' }, units)).toBeCloseTo(0.3, 12);
  });

  it('rejeita valor não positivo', () => {
    expect(() => lengthToMeters({ value: 0, unit: 'cm' })).toThrow(/Physical length/);
  });
});

describe('escala real → repeat UV', () => {
  it('estampa de 10 cm em projetor de 2 m (1 unidade = 1 m) → repeat 20', () => {
    const tiling = computePhysicalRepeat({
      projectorWidthScene: 2,
      projectorHeightScene: 2,
      patternWidth: { value: 10, unit: 'cm' },
      patternHeight: { value: 10, unit: 'cm' },
      sceneMetersPerUnit: 1,
    });
    expect(tiling.repeatU).toBeCloseTo(20, 12);
    expect(tiling.repeatV).toBeCloseTo(20, 12);
    expect(tiling.offsetU).toBe(0);
    expect(tiling.offsetV).toBe(0);
  });

  it('mesmo resultado com padrão em mm e projetor em cena calibrada (1 un = 1 cm)', () => {
    // 200 unidades de cena * 0,01 m/un = 2 m; padrão 100 mm = 0,1 m → repeat 20
    const tiling = computePhysicalRepeat({
      projectorWidthScene: 200,
      projectorHeightScene: 150,
      patternWidth: { value: 100, unit: 'mm' },
      patternHeight: { value: 10, unit: 'cm' },
      sceneMetersPerUnit: 0.01,
      offsetU: 0.25,
      offsetV: 0.5,
    });
    expect(tiling.repeatU).toBeCloseTo(20, 12);
    expect(tiling.repeatV).toBeCloseTo(15, 12);
    expect(tiling.offsetU).toBe(0.25);
    expect(tiling.offsetV).toBe(0.5);
  });

  it('cm e mm equivalentes produzem o mesmo repeat', () => {
    const a = computePhysicalRepeat({
      projectorWidthScene: 1,
      projectorHeightScene: 1,
      patternWidth: { value: 20, unit: 'cm' },
      patternHeight: { value: 5, unit: 'cm' },
      sceneMetersPerUnit: 1,
    });
    const b = computePhysicalRepeat({
      projectorWidthScene: 1,
      projectorHeightScene: 1,
      patternWidth: { value: 200, unit: 'mm' },
      patternHeight: { value: 50, unit: 'mm' },
      sceneMetersPerUnit: 1,
    });
    expect(a.repeatU).toBeCloseTo(b.repeatU, 12);
    expect(a.repeatV).toBeCloseTo(b.repeatV, 12);
  });

  it('rejeita fator de escala inválido', () => {
    expect(() => sceneExtentToMeters(1, 0)).toThrow(/sceneMetersPerUnit/);
  });
});

describe('adesivo: tamanho físico → frustum de cena', () => {
  it('30 × 45 cm com 1 un = 1 m → 0,30 × 0,45', () => {
    const extents = physicalSizeToSceneExtents(
      {
        width: { value: 30, unit: 'cm' },
        height: { value: 45, unit: 'cm' },
      },
      1,
    );
    expect(extents.width).toBeCloseTo(0.3, 12);
    expect(extents.height).toBeCloseTo(0.45, 12);
  });

  it('30 × 45 cm com 1 un = 1 cm → 30 × 45', () => {
    const extents = physicalSizeToSceneExtents(
      {
        width: { value: 30, unit: 'cm' },
        height: { value: 45, unit: 'cm' },
      },
      0.01,
    );
    expect(extents.width).toBeCloseTo(30, 12);
    expect(extents.height).toBeCloseTo(45, 12);
  });
});

describe('resolveTiling / resolveProjectorSizeScene', () => {
  const units = createFallbackUnitsPort(1);

  it('wallpaper com physicalSize deriva repeat do scale do projetor', () => {
    const overlay = createOverlay({
      kind: 'wallpaper',
      textureRef: 'paper.png',
      physicalSize: {
        width: { value: 10, unit: 'cm' },
        height: { value: 10, unit: 'cm' },
      },
      transform: { scale: { x: 2, y: 1, z: 0.4 } },
    });
    const tiling = resolveTiling(overlay, units);
    expect(tiling.repeatU).toBeCloseTo(20, 12);
    expect(tiling.repeatV).toBeCloseTo(10, 12);
  });

  it('wallpaper com tiling explícito ignora o cálculo físico', () => {
    const overlay = createOverlay({
      kind: 'wallpaper',
      textureRef: 'paper.png',
      tiling: { repeatU: 4, repeatV: 2, offsetU: 0.1 },
      physicalSize: {
        width: { value: 10, unit: 'cm' },
        height: { value: 10, unit: 'cm' },
      },
    });
    expect(resolveTiling(overlay, units)).toEqual({
      repeatU: 4,
      repeatV: 2,
      offsetU: 0.1,
      offsetV: 0,
    });
  });

  it('sticker usa physicalSize no frustum e repeat 1×1', () => {
    const overlay = createOverlay({
      kind: 'sticker',
      textureRef: 'logo.png',
      physicalSize: {
        width: { value: 30, unit: 'cm' },
        height: { value: 45, unit: 'cm' },
      },
      tiling: { repeatU: 8, repeatV: 8, offsetU: 0.2 },
    });
    expect(resolveTiling(overlay, units)).toEqual({
      repeatU: 1,
      repeatV: 1,
      offsetU: 0.2,
      offsetV: 0,
    });
    const box = resolveProjectorSizeScene(overlay, units);
    expect(box.width).toBeCloseTo(0.3, 12);
    expect(box.height).toBeCloseTo(0.45, 12);
  });

  it('paint com physicalSize dimensiona o frustum em unidades de cena', () => {
    const overlay = createOverlay({
      kind: 'paint',
      color: '#336699',
      physicalSize: {
        width: { value: 2, unit: 'm' },
        height: { value: 1, unit: 'm' },
      },
    });
    const box = resolveProjectorSizeScene(overlay, units);
    expect(box.width).toBeCloseTo(2, 12);
    expect(box.height).toBeCloseTo(1, 12);
  });
});
