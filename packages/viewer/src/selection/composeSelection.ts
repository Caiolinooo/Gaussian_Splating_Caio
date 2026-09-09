/**
 * Composição de seleções por modo (replace/add/subtract/intersect).
 *
 * Módulo PURO: só arrays tipados e `Set`. Nenhuma entrada é mutada —
 * todo resultado é um `Uint32Array` NOVO, ordenado de forma crescente
 * (invariante exigido pela busca binária de `SelectionManager.has`).
 */

import { assertNever } from '../assertNever';

/** Modo de composição da seleção (espelha `SelectMode` do contrato do renderer). */
export type SelectMode = 'replace' | 'add' | 'subtract' | 'intersect';

/** Converte seleção (possivelmente nula) em conjunto de índices. */
function toSet(indices: Uint32Array | null): Set<number> {
  const set = new Set<number>();
  if (!indices) {
    return set;
  }
  for (const index of indices) {
    set.add(index);
  }
  return set;
}

/** Materializa o conjunto em um `Uint32Array` novo e ordenado. */
function sortedFromSet(set: Set<number>): Uint32Array {
  const out = new Uint32Array(set.size);
  let i = 0;
  for (const value of [...set].sort((a, b) => a - b)) {
    out[i] = value;
    i += 1;
  }
  return out;
}

/** Cópia ordenada (e deduplicada) de um array de índices. */
function sortedCopy(indices: Uint32Array): Uint32Array {
  return sortedFromSet(toSet(indices));
}

/**
 * Compõe a seleção `current` com os índices `incoming` segundo `mode`.
 *
 * - `replace`: resultado é `incoming`.
 * - `add`: união.
 * - `subtract`: `current` menos `incoming` (vazio se `current` for nulo).
 * - `intersect`: interseção (vazia se `current` for nulo).
 *
 * @param current seleção atual (índices ordenados) ou `null` para "nenhuma".
 * @param incoming índices novos (não precisam estar ordenados nem únicos).
 * @param mode modo de composição.
 */
export function composeSelection(
  current: Uint32Array | null,
  incoming: Uint32Array,
  mode: SelectMode,
): Uint32Array {
  switch (mode) {
    case 'replace':
      return sortedCopy(incoming);

    case 'add': {
      const union = toSet(current);
      for (const index of incoming) {
        union.add(index);
      }
      return sortedFromSet(union);
    }

    case 'subtract': {
      const result = toSet(current);
      for (const index of incoming) {
        result.delete(index);
      }
      return sortedFromSet(result);
    }

    case 'intersect': {
      if (!current || current.length === 0) {
        return new Uint32Array(0);
      }
      const incomingSet = toSet(incoming);
      const intersection = new Set<number>();
      for (const index of current) {
        if (incomingSet.has(index)) {
          intersection.add(index);
        }
      }
      return sortedFromSet(intersection);
    }

    default:
      return assertNever(mode, `Modo de seleção desconhecido: ${String(mode)}`);
  }
}
