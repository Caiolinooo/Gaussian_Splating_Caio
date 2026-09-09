import { describe, expect, it } from 'vitest';

import type { RegionShape } from '../renderer/SplatRenderer';
import {
  applyColorAdjust,
  DEFAULT_APPEARANCE,
  isInsideRegion,
} from './SplatEditor';

/**
 * Cria um buffer RGB de 3 floats com os valores informados.
 * `applyColorAdjust` escreve no próprio buffer, em `offset`.
 */
function rgb(r: number, g: number, b: number): Float32Array {
  return new Float32Array([r, g, b]);
}

const S = Math.SQRT1_2; // seno/cosseno de 45° → quaternion de 90° em Z

describe('applyColorAdjust', () => {
  it('com brightness 1 (e saturação/temperatura neutros) mantém a cor idêntica', () => {
    const cores = rgb(0.2, 0.5, 0.8);
    applyColorAdjust(cores, 0, 1, 1, 0);

    expect(cores[0]).toBeCloseTo(0.2, 5);
    expect(cores[1]).toBeCloseTo(0.5, 5);
    expect(cores[2]).toBeCloseTo(0.8, 5);
  });

  it('com brightness 0 resulta em preto', () => {
    const cores = rgb(0.2, 0.5, 0.8);
    applyColorAdjust(cores, 0, 0, 1, 0);

    expect(cores[0]).toBeCloseTo(0, 5);
    expect(cores[1]).toBeCloseTo(0, 5);
    expect(cores[2]).toBeCloseTo(0, 5);
  });

  it('com brightness 2 dobra a intensidade (até o clamp)', () => {
    const cores = rgb(0.1, 0.2, 0.3);
    applyColorAdjust(cores, 0, 2, 1, 0);

    expect(cores[0]).toBeCloseTo(0.2, 5);
    expect(cores[1]).toBeCloseTo(0.4, 5);
    expect(cores[2]).toBeCloseTo(0.6, 5);
  });

  it('com saturation 0 resulta em cinza (r == g == b)', () => {
    const cores = rgb(0.9, 0.4, 0.1);
    applyColorAdjust(cores, 0, 1, 0, 0);

    const r = cores[0] ?? 0;
    const g = cores[1] ?? 0;
    const b = cores[2] ?? 0;
    expect(r).toBeCloseTo(g, 5);
    expect(g).toBeCloseTo(b, 5);

    // luminância de Rec.709: 0.2126*0.9 + 0.7152*0.4 + 0.0722*0.1
    const luminancia = 0.2126 * 0.9 + 0.7152 * 0.4 + 0.0722 * 0.1;
    expect(cores[0]).toBeCloseTo(luminancia, 5);
  });

  it('com temperatura positiva aumenta R e reduz B', () => {
    const cores = rgb(0.5, 0.5, 0.5);
    applyColorAdjust(cores, 0, 1, 1, 0.5);

    expect(cores[0]).toBeCloseTo(0.55, 5); // 0.5 + 0.5*0.1
    expect(cores[1]).toBeCloseTo(0.5, 5); // verde não é afetado
    expect(cores[2]).toBeCloseTo(0.45, 5); // 0.5 - 0.5*0.1
    expect(cores[0]).toBeGreaterThan(0.5);
    expect(cores[2]).toBeLessThan(0.5);
  });

  it('com temperatura negativa reduz R e aumenta B', () => {
    const cores = rgb(0.5, 0.5, 0.5);
    applyColorAdjust(cores, 0, 1, 1, -0.5);

    expect(cores[0]).toBeCloseTo(0.45, 5);
    expect(cores[2]).toBeCloseTo(0.55, 5);
  });

  it('nunca sai de [0,1] (clampeado)', () => {
    // brightness alto estoura para 1
    const quente = rgb(0.5, 0.5, 0.5);
    applyColorAdjust(quente, 0, 10, 1, 0);
    expect(quente[0]).toBe(1);
    expect(quente[1]).toBe(1);
    expect(quente[2]).toBe(1);

    // temperatura muito negativa empurra R para 0 e B para 1
    const frio = rgb(0.2, 0.4, 0.6);
    applyColorAdjust(frio, 0, 0.2, 1, -10);
    expect(frio[0]).toBe(0);
    expect(frio[2]).toBe(1);
    expect(frio[1]).toBeGreaterThanOrEqual(0);
    expect(frio[1]).toBeLessThanOrEqual(1);

    // temperatura muito positiva empurra R para 1 e B para 0
    const muito_quente = rgb(0.2, 0.4, 0.6);
    applyColorAdjust(muito_quente, 0, 0.2, 1, 10);
    expect(muito_quente[0]).toBe(1);
    expect(muito_quente[2]).toBe(0);

    // saturação extrema também fica no intervalo
    const saturado = rgb(0.2, 0.9, 0.4);
    applyColorAdjust(saturado, 0, 1, 100, 0);
    for (const canal of saturado) {
      expect(canal).toBeGreaterThanOrEqual(0);
      expect(canal).toBeLessThanOrEqual(1);
    }
  });

  it('escreve a partir do offset informado sem tocar nos demais canais', () => {
    const cores = new Float32Array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]);
    applyColorAdjust(cores, 3, 0, 1, 0);

    expect(cores[0]).toBeCloseTo(0.1, 5);
    expect(cores[1]).toBeCloseTo(0.2, 5);
    expect(cores[2]).toBeCloseTo(0.3, 5);
    expect(cores[3]).toBeCloseTo(0, 5);
    expect(cores[4]).toBeCloseTo(0, 5);
    expect(cores[5]).toBeCloseTo(0, 5);
  });
});

describe('isInsideRegion — sphere', () => {
  const shape: RegionShape = {
    type: 'sphere',
    center: { x: 1, y: 2, z: 3 },
    radius: 2,
  };

  it('aceita o ponto no centro', () => {
    expect(isInsideRegion(1, 2, 3, shape)).toBe(true);
  });

  it('aceita o ponto exatamente na borda (superfície inclusiva)', () => {
    expect(isInsideRegion(3, 2, 3, shape)).toBe(true); // +2 em X
    expect(isInsideRegion(1, 0, 3, shape)).toBe(true); // -2 em Y
    expect(isInsideRegion(1, 2, 5, shape)).toBe(true); // +2 em Z
  });

  it('rejeita o ponto fora do raio', () => {
    expect(isInsideRegion(4, 2, 3, shape)).toBe(false);
    expect(isInsideRegion(1, 2, 0, shape)).toBe(false);
  });
});

describe('isInsideRegion — box', () => {
  const cubo: RegionShape = {
    type: 'box',
    center: { x: 0, y: 0, z: 0 },
    size: { x: 2, y: 2, z: 2 },
  };

  it('aceita ponto interno e de face, rejeita ponto externo', () => {
    expect(isInsideRegion(0.5, -0.5, 0.9, cubo)).toBe(true);
    expect(isInsideRegion(1, 0, 0, cubo)).toBe(true); // face inclusiva
    expect(isInsideRegion(0, 0, 1.0001, cubo)).toBe(false);
    expect(isInsideRegion(2, 0, 0, cubo)).toBe(false);
  });

  it('respeita o centro do box', () => {
    const deslocado: RegionShape = {
      type: 'box',
      center: { x: 10, y: 0, z: 0 },
      size: { x: 2, y: 2, z: 2 },
    };
    expect(isInsideRegion(10, 0, 0, deslocado)).toBe(true);
    expect(isInsideRegion(0, 0, 0, deslocado)).toBe(false);
  });

  it('com rotação de 90° em Z troca o que está dentro e fora', () => {
    // Box 4 × 1 × 1: sem rotação é longo em X; com 90° em Z fica longo em Y.
    const alongadoX: RegionShape = {
      type: 'box',
      center: { x: 0, y: 0, z: 0 },
      size: { x: 4, y: 1, z: 1 },
    };
    const rotacionado: RegionShape = {
      type: 'box',
      center: { x: 0, y: 0, z: 0 },
      size: { x: 4, y: 1, z: 1 },
      rotation: { x: 0, y: 0, z: S, w: S },
    };

    // (1.5, 0, 0): dentro sem rotação, fora com rotação.
    expect(isInsideRegion(1.5, 0, 0, alongadoX)).toBe(true);
    expect(isInsideRegion(1.5, 0, 0, rotacionado)).toBe(false);

    // (0, 1.5, 0): fora sem rotação, dentro com rotação.
    expect(isInsideRegion(0, 1.5, 0, alongadoX)).toBe(false);
    expect(isInsideRegion(0, 1.5, 0, rotacionado)).toBe(true);
  });
});

describe('isInsideRegion — plane', () => {
  const shape: RegionShape = {
    type: 'plane',
    point: { x: 0, y: 0, z: 0 },
    normal: { x: 0, y: 1, z: 0 },
  };

  it('aceita o ponto do lado para onde a normal aponta', () => {
    expect(isInsideRegion(0, 5, 0, shape)).toBe(true);
    expect(isInsideRegion(10, 0.001, -10, shape)).toBe(true);
  });

  it('rejeita o ponto do lado oposto', () => {
    expect(isInsideRegion(0, -5, 0, shape)).toBe(false);
  });

  it('aceita o ponto exatamente sobre o plano (>= 0)', () => {
    expect(isInsideRegion(3, 0, -7, shape)).toBe(true);
  });

  it('respeita o ponto de referência do plano', () => {
    const elevado: RegionShape = {
      type: 'plane',
      point: { x: 0, y: 10, z: 0 },
      normal: { x: 0, y: 1, z: 0 },
    };
    expect(isInsideRegion(0, 10, 0, elevado)).toBe(true);
    expect(isInsideRegion(0, 9, 0, elevado)).toBe(false);
  });
});

describe('DEFAULT_APPEARANCE', () => {
  it('começa neutro (sem alterar brilho, saturação, temperatura ou opacidade)', () => {
    expect(DEFAULT_APPEARANCE.brightness).toBe(1);
    expect(DEFAULT_APPEARANCE.saturation).toBe(1);
    expect(DEFAULT_APPEARANCE.temperature).toBe(0);
    expect(DEFAULT_APPEARANCE.opacity).toBe(1);
  });

  it('é congelado (não pode ser mutado por engano)', () => {
    expect(Object.isFrozen(DEFAULT_APPEARANCE)).toBe(true);
  });
});
