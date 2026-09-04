import { describe, expect, it } from 'vitest';

import {
  blendModeToIndex,
  isStickerOverlay,
  overlayKindToIndex,
  type BlendMode,
  type OverlayKind,
} from '../src/types';
import {
  OverlayValidationError,
  createOverlay,
  mergeOverlay,
  validateOverlay,
} from '../src/validate';

describe('validação do modelo', () => {
  it('sticker sem physicalSize → erro', () => {
    expect(() =>
      validateOverlay({
        id: 'st-1',
        kind: 'sticker',
        textureRef: 'logo.png',
      }),
    ).toThrow(OverlayValidationError);

    try {
      validateOverlay({
        id: 'st-1',
        kind: 'sticker',
        textureRef: 'logo.png',
      });
    } catch (error) {
      expect(error).toBeInstanceOf(OverlayValidationError);
      expect((error as OverlayValidationError).issues.join(' ')).toMatch(/physicalSize/);
    }
  });

  it('sticker de 30 × 45 cm é aceito', () => {
    const sticker = createOverlay({
      kind: 'sticker',
      textureRef: 'logo.png',
      physicalSize: {
        width: { value: 30, unit: 'cm' },
        height: { value: 45, unit: 'cm' },
      },
    });
    expect(isStickerOverlay(sticker)).toBe(true);
    if (!isStickerOverlay(sticker)) {
      return;
    }
    expect(sticker.physicalSize.width).toEqual({ value: 30, unit: 'cm' });
    expect(sticker.physicalSize.height).toEqual({ value: 45, unit: 'cm' });
    expect(sticker.opacity).toBe(1);
    expect(sticker.maskByNormal.enabled).toBe(true);
    expect(sticker.maskByNormal.threshold).toBe(0.5);
  });

  it('wallpaper sem tiling e sem physicalSize → erro', () => {
    expect(() =>
      createOverlay({
        kind: 'wallpaper',
        textureRef: 'paper.png',
      }),
    ).toThrow(/tiling or physicalSize/);
  });

  it('paint sem color → erro', () => {
    expect(() =>
      validateOverlay({
        id: 'p1',
        kind: 'paint',
      }),
    ).toThrow(/color/);
  });

  it('rejeita opacity fora de [0, 1]', () => {
    expect(() =>
      createOverlay({
        kind: 'paint',
        color: '#fff',
        opacity: 1.2,
      }),
    ).toThrow(/opacity/);
  });

  it('rejeita blendMode desconhecido', () => {
    expect(() =>
      validateOverlay({
        id: 'p1',
        kind: 'paint',
        color: '#abcdef',
        blendMode: 'screen',
      }),
    ).toThrow(/blendMode/);
  });

  it('rejeita kind desconhecido', () => {
    expect(() =>
      validateOverlay({
        id: 'x',
        kind: 'decal',
      }),
    ).toThrow(/kind/);
  });

  it('wallpaper válido com tiling explícito', () => {
    const paper = createOverlay({
      kind: 'wallpaper',
      textureRef: 'damask.png',
      tiling: { repeatU: 6, repeatV: 3 },
      color: '#ffffff',
    });
    expect(paper.kind).toBe('wallpaper');
    expect(paper.tiling?.repeatU).toBe(6);
  });

  it('mergeOverlay atualiza opacidade e máscara sem perder physicalSize', () => {
    const sticker = createOverlay({
      id: 'st-keep',
      kind: 'sticker',
      textureRef: 'a.png',
      physicalSize: {
        width: { value: 30, unit: 'cm' },
        height: { value: 45, unit: 'cm' },
      },
    });
    const next = mergeOverlay(sticker, {
      opacity: 0.4,
      maskByNormal: { threshold: 0.7 },
    });
    expect(next.kind).toBe('sticker');
    expect(next.opacity).toBe(0.4);
    expect(next.maskByNormal.threshold).toBe(0.7);
    expect(next.maskByNormal.enabled).toBe(true);
    expect(next.physicalSize).toEqual(sticker.physicalSize);
  });
});

describe('índices de shader (switch exhaustivo)', () => {
  it('mapeia kind e blendMode', () => {
    const kinds: OverlayKind[] = ['paint', 'wallpaper', 'sticker'];
    expect(kinds.map(overlayKindToIndex)).toEqual([0, 1, 2]);

    const modes: BlendMode[] = ['normal', 'multiply', 'overlay'];
    expect(modes.map(blendModeToIndex)).toEqual([0, 1, 2]);
  });
});
