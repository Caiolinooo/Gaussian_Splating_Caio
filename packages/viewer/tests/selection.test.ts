import { describe, expect, it } from 'vitest';

import {
  composeSelection,
  pointInBox,
  pointInPolygon,
  pointInRect,
  pointInSphere,
  projectCenter,
  SelectionManager,
} from '../src/selection';
import type { SelectMode } from '../src/selection';

/** viewProjection identidade: NDC == mundo (w = 1). */
const IDENTITY = new Float32Array([
  1, 0, 0, 0,
  0, 1, 0, 0,
  0, 0, 1, 0,
  0, 0, 0, 1,
]);

const VIEWPORT = { width: 800, height: 600 };

describe('projectCenter', () => {
  it('projeta o centro da tela com matriz identidade', () => {
    const p = projectCenter(0, 0, 0, IDENTITY, VIEWPORT);
    expect(p.px).toBeCloseTo(400);
    expect(p.py).toBeCloseTo(300);
    expect(p.visible).toBe(true);
  });

  it('inverte Y (origem topo-esquerdo)', () => {
    const top = projectCenter(0, 1, 0, IDENTITY, VIEWPORT);
    const bottom = projectCenter(0, -1, 0, IDENTITY, VIEWPORT);
    expect(top.py).toBeLessThan(bottom.py);
    expect(top.py).toBeCloseTo(0);
    expect(bottom.py).toBeCloseTo(600);
  });

  it('marca invisível atrás da câmera (w <= 0)', () => {
    // Matriz que zera w (última linha nula) → w = 0.
    const zeroW = new Float32Array(16);
    const p = projectCenter(1, 2, 3, zeroW, VIEWPORT);
    expect(p.visible).toBe(false);
  });

  it('marca invisível fora do frustum em Z', () => {
    // z = 5 com matriz identidade → ndcZ = 5, fora de [-1, 1].
    const p = projectCenter(0, 0, 5, IDENTITY, VIEWPORT);
    expect(p.visible).toBe(false);
    expect(p.ndcZ).toBeCloseTo(5);
  });

  it('marca invisível fora das bordas X/Y', () => {
    expect(projectCenter(2, 0, 0, IDENTITY, VIEWPORT).visible).toBe(false);
    expect(projectCenter(0, -2, 0, IDENTITY, VIEWPORT).visible).toBe(false);
  });

  it('aplica translação da matriz (coluna 3 = m[12..14])', () => {
    const shifted = new Float32Array(IDENTITY);
    shifted[12] = 1; // move +1 em X no clip space
    const p = projectCenter(0, 0, 0, shifted, VIEWPORT);
    expect(p.px).toBeCloseTo(800); // ndcX = 1 → borda direita
  });
});

describe('pointInRect / pointInPolygon', () => {
  it('testa retângulo com bordas inclusivas', () => {
    const rect = { x: 10, y: 10, width: 100, height: 50 };
    expect(pointInRect(10, 10, rect)).toBe(true);
    expect(pointInRect(110, 60, rect)).toBe(true);
    expect(pointInRect(9, 10, rect)).toBe(false);
    expect(pointInRect(10, 61, rect)).toBe(false);
  });

  it('normaliza retângulo com largura/altura negativas', () => {
    const rect = { x: 110, y: 60, width: -100, height: -50 };
    expect(pointInRect(60, 40, rect)).toBe(true);
    expect(pointInRect(5, 40, rect)).toBe(false);
  });

  it('polígono com menos de 3 pontos retorna false', () => {
    expect(pointInPolygon(0, 0, [])).toBe(false);
    expect(pointInPolygon(0, 0, [{ x: 0, y: 0 }])).toBe(false);
    expect(
      pointInPolygon(0, 0, [
        { x: 0, y: 0 },
        { x: 1, y: 1 },
      ]),
    ).toBe(false);
  });

  it('raio par-ímpar: ponto dentro do quadrado', () => {
    const square = [
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 10, y: 10 },
      { x: 0, y: 10 },
    ];
    expect(pointInPolygon(5, 5, square)).toBe(true);
    expect(pointInPolygon(15, 5, square)).toBe(false);
    expect(pointInPolygon(-1, 5, square)).toBe(false);
  });

  it('raio par-ímpar: ponto em forma côncava (U com recorte vindo de cima)', () => {
    // Retângulo 0..10 x 0..10 com entalhe 3..7 no topo (de y=10 até y=4).
    const u = [
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 10, y: 10 },
      { x: 7, y: 10 },
      { x: 7, y: 4 },
      { x: 3, y: 4 },
      { x: 3, y: 10 },
      { x: 0, y: 10 },
    ];
    expect(pointInPolygon(5, 2, u)).toBe(true); // base do U (abaixo do entalhe)
    expect(pointInPolygon(1, 8, u)).toBe(true); // perna esquerda
    expect(pointInPolygon(9, 8, u)).toBe(true); // perna direita
    expect(pointInPolygon(5, 8, u)).toBe(false); // dentro do entalhe
    expect(pointInPolygon(5, 5, u)).toBe(false); // dentro do entalhe
    expect(pointInPolygon(15, 5, u)).toBe(false); // fora do polígono
  });
});

describe('pointInSphere / pointInBox', () => {
  it('esfera: dentro, na borda e fora', () => {
    const sphere = { center: { x: 0, y: 0, z: 0 }, radius: 2 };
    expect(pointInSphere(1, 1, 1, sphere)).toBe(true); // √3 < 2
    expect(pointInSphere(2, 0, 0, sphere)).toBe(true); // borda inclusiva
    expect(pointInSphere(3, 0, 0, sphere)).toBe(false);
  });

  it('box sem rotação (AABB)', () => {
    const box = { center: { x: 0, y: 0, z: 0 }, size: { x: 2, y: 2, z: 2 } };
    expect(pointInBox(1, 1, 1, box)).toBe(true); // face inclusiva
    expect(pointInBox(1.1, 0, 0, box)).toBe(false);
  });

  it('box rotacionado 90° em Z troca os eixos', () => {
    // Rotação de 90° em torno de Z: eixo X local aponta para Y do mundo.
    const s = Math.SQRT1_2;
    const box = {
      center: { x: 0, y: 0, z: 0 },
      size: { x: 4, y: 1, z: 1 },
      rotation: { x: 0, y: 0, z: s, w: s },
    };
    expect(pointInBox(0, 2, 0, box)).toBe(true); // face do eixo longo rotacionado
    expect(pointInBox(0, 1.5, 0, box)).toBe(true); // ao longo do eixo longo
    expect(pointInBox(0, 2.5, 0, box)).toBe(false); // além do eixo longo
    expect(pointInBox(1.5, 0, 0, box)).toBe(false); // eixo curto
  });
});

describe('composeSelection', () => {
  const current = new Uint32Array([1, 2, 3, 5]);
  const incoming = new Uint32Array([3, 4, 6]);

  it('replace devolve apenas incoming', () => {
    expect([...composeSelection(current, incoming, 'replace')]).toEqual([3, 4, 6]);
  });

  it('add faz a união ordenada', () => {
    expect([...composeSelection(current, incoming, 'add')]).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it('subtract remove incoming de current', () => {
    expect([...composeSelection(current, incoming, 'subtract')]).toEqual([1, 2, 5]);
  });

  it('intersect mantém a interseção', () => {
    expect([...composeSelection(current, incoming, 'intersect')]).toEqual([3]);
  });

  it('current nulo: add = incoming, subtract/intersect = vazio', () => {
    expect([...composeSelection(null, incoming, 'add')]).toEqual([3, 4, 6]);
    expect(composeSelection(null, incoming, 'subtract').length).toBe(0);
    expect(composeSelection(null, incoming, 'intersect').length).toBe(0);
  });

  it('não muta as entradas e ordena/deduzplica', () => {
    const a = new Uint32Array([5, 1, 3]);
    const b = new Uint32Array([3, 9]);
    const out = composeSelection(a, b, 'add');
    expect([...a]).toEqual([5, 1, 3]);
    expect([...b]).toEqual([3, 9]);
    expect([...out]).toEqual([1, 3, 5, 9]);
    expect([...composeSelection(null, a, 'replace')]).toEqual([1, 3, 5]);
  });

  it('modos válidos cobrem o tipo SelectMode', () => {
    const modes: SelectMode[] = ['replace', 'add', 'subtract', 'intersect'];
    for (const mode of modes) {
      expect(composeSelection(current, incoming, mode)).toBeInstanceOf(Uint32Array);
    }
  });
});

describe('SelectionManager', () => {
  const centers = new Float32Array([
    0, 0, 0,
    1, 1, 1,
    -2, -2, -2,
    10, 10, 10,
  ]);

  it('começa vazio', () => {
    const sm = new SelectionManager();
    expect(sm.getCount()).toBe(0);
    expect(sm.getIndices().length).toBe(0);
    expect(sm.getBounds(centers)).toBeNull();
    expect(sm.has(0)).toBe(false);
  });

  it('has() por busca binária acerta em todos os índices', () => {
    const sm = new SelectionManager();
    sm.set(new Uint32Array([5, 1, 3, 9]));
    for (const i of [1, 3, 5, 9]) {
      expect(sm.has(i)).toBe(true);
    }
    for (const i of [0, 2, 4, 6, 7, 8, 10, 100]) {
      expect(sm.has(i)).toBe(false);
    }
  });

  it('apply compõe e atualiza o estado', () => {
    const sm = new SelectionManager();
    sm.apply(new Uint32Array([0, 1]), 'add');
    expect(sm.getCount()).toBe(2);
    sm.apply(new Uint32Array([2]), 'add');
    expect([...sm.getIndices()]).toEqual([0, 1, 2]);
    sm.apply(new Uint32Array([1]), 'subtract');
    expect([...sm.getIndices()]).toEqual([0, 2]);
    const result = sm.apply(new Uint32Array([0, 5]), 'intersect');
    expect([...result]).toEqual([0]);
    expect([...sm.getIndices()]).toEqual([0]);
  });

  it('apply retorna cópia (mutar o resultado não afeta o estado)', () => {
    const sm = new SelectionManager();
    const out = sm.apply(new Uint32Array([1, 2]), 'add');
    out[0] = 99;
    expect([...sm.getIndices()]).toEqual([1, 2]);
  });

  it('snapshot é cópia defensiva', () => {
    const sm = new SelectionManager();
    sm.set(new Uint32Array([1, 2]));
    const snap = sm.snapshot();
    snap[0] = 42;
    expect([...sm.getIndices()]).toEqual([1, 2]);
  });

  it('getBounds calcula a AABB dos centros selecionados', () => {
    const sm = new SelectionManager();
    sm.set(new Uint32Array([0, 1, 2]));
    const bounds = sm.getBounds(centers);
    expect(bounds).not.toBeNull();
    expect(bounds?.min).toEqual([-2, -2, -2]);
    expect(bounds?.max).toEqual([1, 1, 1]);
  });

  it('getBounds ignora índices fora do buffer', () => {
    const sm = new SelectionManager();
    sm.set(new Uint32Array([3, 99]));
    const bounds = sm.getBounds(centers);
    expect(bounds?.min).toEqual([10, 10, 10]);
    expect(bounds?.max).toEqual([10, 10, 10]);
  });

  it('clear zera o estado', () => {
    const sm = new SelectionManager();
    sm.set(new Uint32Array([1, 2, 3]));
    sm.clear();
    expect(sm.getCount()).toBe(0);
    expect(sm.getBounds(centers)).toBeNull();
  });
});
