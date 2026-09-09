import { describe, expect, it } from 'vitest';

import {
  decimateSplats,
  mergeSplats,
  type DecimateParams,
  type SplatArrays,
} from './decimate';

/* ------------------------------------------------------------------ *
 * Helpers determinísticos (sem Math.random)
 * ------------------------------------------------------------------ */

interface MakeSplatsOptions {
  /** Distância entre centros consecutivos ao longo de X. */
  spacing?: number;
  /** Escala uniforme (desvio-padrão) nos três eixos. */
  scale?: number;
  /** Opacidade por índice. */
  opacity?: (i: number) => number;
  /** Cor RGB (0–1) por índice. */
  color?: (i: number) => [number, number, number];
}

/**
 * Cria `n` splats alinhados no eixo X, todos com a mesma escala, cor e
 * rotação identidade — ou seja, todos candidatos a merge entre si.
 */
function makeSplats(n: number, options: MakeSplatsOptions = {}): SplatArrays {
  const spacing = options.spacing ?? 0.02;
  const scale = options.scale ?? 1;
  const opacityOf = options.opacity ?? (() => 0.5);
  const colorOf = options.color ?? (() => [0.4, 0.6, 0.8] as [number, number, number]);

  const centers = new Float32Array(n * 3);
  const scales = new Float32Array(n * 3);
  const quaternions = new Float32Array(n * 4);
  const opacities = new Float32Array(n);
  const colors = new Float32Array(n * 3);

  for (let i = 0; i < n; i += 1) {
    const c = i * 3;
    const q = i * 4;

    centers[c] = i * spacing;
    centers[c + 1] = 0;
    centers[c + 2] = 0;

    scales[c] = scale;
    scales[c + 1] = scale;
    scales[c + 2] = scale;

    // rotação identidade (0, 0, 0, 1)
    quaternions[q] = 0;
    quaternions[q + 1] = 0;
    quaternions[q + 2] = 0;
    quaternions[q + 3] = 1;

    opacities[i] = opacityOf(i);

    const rgb = colorOf(i);
    colors[c] = rgb[0];
    colors[c + 1] = rgb[1];
    colors[c + 2] = rgb[2];
  }

  return { centers, scales, quaternions, opacities, colors };
}

interface RawSplat {
  center: [number, number, number];
  scale: [number, number, number];
  opacity: number;
  color: [number, number, number];
}

function makeSplatPair(a: RawSplat, b: RawSplat): SplatArrays {
  const splats = makeSplats(2);
  writeRawSplat(splats, 0, a);
  writeRawSplat(splats, 1, b);
  return splats;
}

function writeRawSplat(splats: SplatArrays, index: number, s: RawSplat): void {
  const c = index * 3;
  splats.centers.set(s.center, c);
  splats.scales.set(s.scale, c);
  splats.colors.set(s.color, c);
  splats.opacities[index] = s.opacity;
}

function snapshotOf(splats: SplatArrays) {
  return {
    centers: splats.centers.slice(),
    scales: splats.scales.slice(),
    quaternions: splats.quaternions.slice(),
    opacities: splats.opacities.slice(),
    colors: splats.colors.slice(),
  };
}

/* ------------------------------------------------------------------ *
 * decimateSplats
 * ------------------------------------------------------------------ */

describe('decimateSplats', () => {
  it('não altera nada quando target >= count', () => {
    const splats = makeSplats(12);

    const igual = decimateSplats(splats, { target: 12 } as DecimateParams);
    expect(igual.count).toBe(12);
    expect(igual.merged).toBe(0);
    expect(igual.removedByOpacity).toBe(0);

    const acima = decimateSplats(makeSplats(12), { target: 999 });
    expect(acima.count).toBe(12);
    expect(acima.merged).toBe(0);
    expect(acima.removedByOpacity).toBe(0);
  });

  it('reduz a contagem quando target < count e há pares compatíveis', () => {
    const splats = makeSplats(20);
    const result = decimateSplats(splats, { target: 10 });

    expect(result.merged).toBe(10);
    expect(result.count).toBe(10);
    expect(result.count).toBeLessThan(20);
    expect(result.removedByOpacity).toBe(0);
  });

  it('preserva a contagem quando nenhum par é compatível', () => {
    // Centros a 50 unidades, escala 0.01: nenhum par passa no teste de
    // distância (maxDistanceFactor 0.5 × escala média = 0.005).
    const splats = makeSplats(6, { spacing: 50, scale: 0.01 });
    const result = decimateSplats(splats, { target: 1 });

    expect(result.merged).toBe(0);
    expect(result.count).toBe(6);
  });

  it('descarta splats com opacidade abaixo de minOpacity', () => {
    const splats = makeSplats(10, { opacity: (i) => (i < 4 ? 0.01 : 0.8) });
    const result = decimateSplats(splats, { target: 3, minOpacity: 0.1 });

    expect(result.removedByOpacity).toBe(4);
    expect(result.count).toBe(3);
  });

  it('devolve contagem zero quando todos caem pelo corte de opacidade', () => {
    const splats = makeSplats(5, { opacity: () => 0.001 });
    const result = decimateSplats(splats, { target: 1, minOpacity: 0.5 });

    expect(result.removedByOpacity).toBe(5);
    expect(result.count).toBe(0);
    expect(result.merged).toBe(0);
  });

  it('não muta as arrays de entrada', () => {
    const splats = makeSplats(16, { opacity: (i) => 0.3 + (i % 5) * 0.1 });
    const antes = snapshotOf(splats);

    const result = decimateSplats(splats, { target: 8 });

    expect(Array.from(splats.centers)).toEqual(Array.from(antes.centers));
    expect(Array.from(splats.scales)).toEqual(Array.from(antes.scales));
    expect(Array.from(splats.quaternions)).toEqual(Array.from(antes.quaternions));
    expect(Array.from(splats.opacities)).toEqual(Array.from(antes.opacities));
    expect(Array.from(splats.colors)).toEqual(Array.from(antes.colors));

    // e o resultado usa buffers novos (não compartilha com a entrada)
    expect(result.centers).not.toBe(splats.centers);
    expect(result.opacities).not.toBe(splats.opacities);
  });

  it('não quebra com array vazio', () => {
    const splats = makeSplats(0);
    const result = decimateSplats(splats, { target: 0 });

    expect(result.count).toBe(0);
    expect(result.merged).toBe(0);
    expect(result.removedByOpacity).toBe(0);
    expect(() => decimateSplats(makeSplats(0), { target: 10 })).not.toThrow();
  });
});

/* ------------------------------------------------------------------ *
 * mergeSplats
 * ------------------------------------------------------------------ */

describe('mergeSplats', () => {
  const A: RawSplat = {
    center: [0, 0, 0],
    scale: [1, 1, 1],
    opacity: 0.4,
    color: [0.2, 0.4, 0.6],
  };
  const B: RawSplat = {
    center: [2, 0, 0],
    scale: [3, 4, 5],
    opacity: 0.6,
    color: [0.8, 0.6, 0.4],
  };

  it('posiciona o centro entre os dois originais (média ponderada por opacidade)', () => {
    const splats = makeSplatPair(A, B);
    const m = mergeSplats(splats, 0, 1);

    // wa = 0.4, wb = 0.6 → ta = 0.4, tb = 0.6 → cx = 0*0.4 + 2*0.6 = 1.2
    expect(m.cx).toBeCloseTo(1.2, 5);
    expect(m.cy).toBeCloseTo(0, 5);
    expect(m.cz).toBeCloseTo(0, 5);

    expect(m.cx).toBeGreaterThanOrEqual(Math.min(A.center[0], B.center[0]));
    expect(m.cx).toBeLessThanOrEqual(Math.max(A.center[0], B.center[0]));
  });

  it('combina opacidades como 1-(1-a1)(1-a2) e nunca passa de 1', () => {
    const splats = makeSplatPair(A, B);
    const m = mergeSplats(splats, 0, 1);

    expect(m.opacity).toBeCloseTo(1 - (1 - 0.4) * (1 - 0.6), 5);
    expect(m.opacity).toBeCloseTo(0.76, 5);
    expect(m.opacity).toBeLessThanOrEqual(1);

    // caso limite: dois splats totalmente opacos continuam em 1.0
    const opacos = makeSplatPair(
      { ...A, opacity: 1 },
      { ...B, opacity: 1 },
    );
    expect(mergeSplats(opacos, 0, 1).opacity).toBeCloseTo(1, 5);
    expect(mergeSplats(opacos, 0, 1).opacity).toBeLessThanOrEqual(1);

    const quase = makeSplatPair(
      { ...A, opacity: 0.999 },
      { ...B, opacity: 0.999 },
    );
    expect(mergeSplats(quase, 0, 1).opacity).toBeLessThanOrEqual(1);
  });

  it('combina escalas em quadratura (sqrt(a² + b²)) em cada eixo', () => {
    const splats = makeSplatPair(
      { center: [0, 0, 0], scale: [3, 0.5, 2], opacity: 0.5, color: [0.4, 0.6, 0.8] },
      { center: [1, 0, 0], scale: [4, 1.2, 0.7], opacity: 0.5, color: [0.4, 0.6, 0.8] },
    );
    const m = mergeSplats(splats, 0, 1);

    expect(m.sx).toBeCloseTo(Math.sqrt(3 * 3 + 4 * 4), 5); // 5
    expect(m.sy).toBeCloseTo(Math.sqrt(0.5 * 0.5 + 1.2 * 1.2), 5); // 1.3
    expect(m.sz).toBeCloseTo(Math.sqrt(2 * 2 + 0.7 * 0.7), 5); // ~2.11896
  });

  it('interpola a cor ponderada por opacidade', () => {
    const splats = makeSplatPair(A, B);
    const m = mergeSplats(splats, 0, 1);

    expect(m.r).toBeCloseTo(0.2 * 0.4 + 0.8 * 0.6, 5);
    expect(m.g).toBeCloseTo(0.4 * 0.4 + 0.6 * 0.6, 5);
    expect(m.b).toBeCloseTo(0.6 * 0.4 + 0.4 * 0.6, 5);
  });

  it('herda a rotação do splat mais opaco', () => {
    const splats = makeSplatPair(
      { ...A, opacity: 0.2 },
      { ...B, opacity: 0.9 },
    );
    splats.quaternions.set([0, 0, 0.7071068, 0.7071068], 0); // rotação de A
    splats.quaternions.set([0.5, 0.5, 0.5, 0.5], 4); // rotação de B

    const m = mergeSplats(splats, 0, 1);

    expect(m.qx).toBeCloseTo(0.5, 5);
    expect(m.qy).toBeCloseTo(0.5, 5);
    expect(m.qz).toBeCloseTo(0.5, 5);
    expect(m.qw).toBeCloseTo(0.5, 5);
  });
});
