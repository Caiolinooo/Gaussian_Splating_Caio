/**
 * Estado da seleção ativa de splats.
 *
 * Módulo PURO: sem `three`, sem DOM. Guarda apenas índices (ordenados e
 * únicos) — os dados de splat (centers/opacities) entram por parâmetro,
 * normalmente vindos de `mesh.forEachSplat()` no backend.
 */

import { composeSelection, type SelectMode } from './composeSelection';

export type { SelectMode };

/** AABB de um conjunto de pontos 3D. */
export interface Bounds3 {
  min: [number, number, number];
  max: [number, number, number];
}

/**
 * Mantém a seleção corrente e aplica operações de composição.
 *
 * Invariante: os índices internos estão sempre ordenados de forma crescente
 * e sem duplicatas (base para `has()` por busca binária).
 */
export class SelectionManager {
  private indices: Uint32Array = new Uint32Array(0);

  constructor(initial?: Uint32Array) {
    if (initial && initial.length > 0) {
      this.indices = composeSelection(null, initial, 'replace');
    }
  }

  /**
   * Índices selecionados (array interno — NÃO mutar).
   * Use `snapshot()` se precisar de uma cópia defensiva.
   */
  getIndices(): Uint32Array {
    return this.indices;
  }

  /** Quantidade de splats selecionados. */
  getCount(): number {
    return this.indices.length;
  }

  /** `true` se o índice está selecionado (busca binária O(log n)). */
  has(i: number): boolean {
    let lo = 0;
    let hi = this.indices.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const value = this.indices[mid];
      if (value === undefined) {
        return false;
      }
      if (value === i) {
        return true;
      }
      if (value < i) {
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    return false;
  }

  /** Substitui a seleção por `indices` (cópia ordenada e deduplicada). */
  set(indices: Uint32Array): void {
    this.indices = composeSelection(null, indices, 'replace');
  }

  /** Limpa a seleção. */
  clear(): void {
    this.indices = new Uint32Array(0);
  }

  /**
   * Compõe `incoming` na seleção atual e atualiza o estado.
   * @returns cópia do novo estado (o array interno não é exposto).
   */
  apply(incoming: Uint32Array, mode: SelectMode): Uint32Array {
    const next = composeSelection(this.indices, incoming, mode);
    this.indices = next;
    return next.slice();
  }

  /**
   * AABB dos centros dos splats selecionados.
   *
   * @param centers centros intercalados (x, y, z por splat).
   * @returns `null` se a seleção estiver vazia ou nenhum índice for válido
   *          (índices fora do buffer são ignorados).
   */
  getBounds(centers: Float32Array): Bounds3 | null {
    if (this.indices.length === 0) {
      return null;
    }

    let minX = Infinity;
    let minY = Infinity;
    let minZ = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    let maxZ = -Infinity;
    let found = false;

    for (const index of this.indices) {
      const base = index * 3;
      const x = centers[base];
      const y = centers[base + 1];
      const z = centers[base + 2];
      if (x === undefined || y === undefined || z === undefined) {
        continue; // índice fora do buffer: ignorado
      }
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (z < minZ) minZ = z;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
      if (z > maxZ) maxZ = z;
      found = true;
    }

    if (!found) {
      return null;
    }

    return { min: [minX, minY, minZ], max: [maxX, maxY, maxZ] };
  }

  /** Cópia defensiva dos índices selecionados. */
  snapshot(): Uint32Array {
    return this.indices.slice();
  }
}
