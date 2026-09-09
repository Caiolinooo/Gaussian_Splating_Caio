/**
 * Decimação de gaussianas por merge de vizinhos similares.
 *
 * O Spark 2.1 não expõe decimação, então este é algoritmo nosso (CPU, puro,
 * testável). A ideia segue o praticado em ferramentas de cleanup de 3DGS:
 *
 * 1. Indexa os splats num grid espacial uniforme (hash por célula).
 * 2. Percorre os splats e procura um parceiro de merge não-consumido dentro do
 *    raio de busca (vizinhança 3×3×3 de células).
 * 3. Dois splats podem ser mergeados se:
 *    - a distância entre centros for menor que `maxDistanceFactor` × escala
 *      média (grosso modo: elipsoides que se sobrepõem de verdade);
 *    - a diferença de escala for inferior a `maxScaleRatio` (evita fundir uma
 *      gaussiana fina de detalhe com uma enorme de fundo);
 *    - a diferença de cor for inferior a `maxColorDistance` (não mistura
 *      materiais diferentes).
 * 4. O merge é uma média ponderada por opacidade de centro e cor; as escalas
 *    combinam em quadratura (soma de variâncias, como na composição de
 *    gaussianas); a opacidade resultante é a união probabilística
 *    `1 - (1-a₁)(1-a₂)`.
 * 5. Splats sem parceiro (ou de opacidade desprezível) são preservados.
 *
 * Complexidade: O(n) esperado, com custo de memória O(n). Para 1M de splats o
 * gargalo é a alocação dos Float32Array — rode em worker se travar a UI.
 */

export interface DecimateParams {
  /** Alvo aproximado de gaussianas após a decimação. */
  target: number;
  /** Tolerância de escala para aceitar merge (razão máxima entre escalas). */
  maxScaleRatio?: number;
  /** Distância máxima entre centros, em múltiplos da escala média do par. */
  maxDistanceFactor?: number;
  /** Distância máxima de cor (0–1 por canal, euclidiana normalizada). */
  maxColorDistance?: number;
  /** Descarta gaussianas com opacidade abaixo disto (0–1). */
  minOpacity?: number;
}

export interface SplatArrays {
  /** xyz intercalado, tamanho 3×count. */
  centers: Float32Array;
  /** escalas (desvio-padrão) xyz intercalado, tamanho 3×count. */
  scales: Float32Array;
  /** quaternions xyzw intercalado, tamanho 4×count. */
  quaternions: Float32Array;
  /** alfa linear 0–1, tamanho count. */
  opacities: Float32Array;
  /** rgb 0–1 intercalado, tamanho 3×count. */
  colors: Float32Array;
}

export interface DecimateResult extends SplatArrays {
  /** Nova contagem (≤ count original). */
  count: number;
  /** Quantos splats foram descartados por opacidade baixa. */
  removedByOpacity: number;
  /** Quantos merges foram realizados. */
  merged: number;
}

const DEFAULT_MAX_SCALE_RATIO = 1.6;
const DEFAULT_MAX_DISTANCE_FACTOR = 0.5;
const DEFAULT_MAX_COLOR_DISTANCE = 0.12;
const DEFAULT_MIN_OPACITY = 0;

/**
 * Reduz `splats` até ~`params.target` gaussianas.
 * NÃO muta as arrays de entrada — devolve arrays novos já cortados em `count`.
 */
export function decimateSplats(
  splats: SplatArrays,
  params: DecimateParams,
): DecimateResult {
  const count = splats.opacities.length;
  if (count === 0 || params.target >= count) {
    return passthrough(splats, count);
  }

  const maxScaleRatio = params.maxScaleRatio ?? DEFAULT_MAX_SCALE_RATIO;
  const maxDistanceFactor = params.maxDistanceFactor ?? DEFAULT_MAX_DISTANCE_FACTOR;
  const maxColorDistance = params.maxColorDistance ?? DEFAULT_MAX_COLOR_DISTANCE;
  const minOpacity = params.minOpacity ?? DEFAULT_MIN_OPACITY;

  // 1. Filtra por opacidade — splats invisíveis não custam qualidade visual.
  const keep = new Uint32Array(count);
  let kept = 0;
  for (let i = 0; i < count; i += 1) {
    if (at(splats.opacities, i) >= minOpacity) {
      keep[kept] = i;
      kept += 1;
    }
  }
  const removedByOpacity = count - kept;
  if (kept === 0) {
    return emptyResult(count);
  }

  // Quantos pares precisamos fundir para bater o alvo.
  const mergesNeeded = Math.max(0, kept - Math.max(1, Math.floor(params.target)));
  if (mergesNeeded === 0) {
    return passthrough(splats, count, removedByOpacity);
  }

  // 2. Grid espacial. Tamanho de célula = mediana aproximada das escalas,
  //    para que a vizinhança 3×3×3 cubra o raio de busca desejado.
  const cell = estimateCellSize(splats, keep, kept);
  const grid = buildGrid(splats, keep, kept, cell);

  const out = allocate(kept);
  const consumed = new Uint8Array(kept);
  let merged = 0;
  let write = 0;

  // 3. Varredura: tenta fundir cada splat vivo com um vizinho compatível.
  for (let a = 0; a < kept && merged < mergesNeeded; a += 1) {
    if (consumed[a]) {
      continue;
    }
    const ia = keep[a];
    if (ia === undefined) {
      continue;
    }
    const partner = findMergePartner({
      splats,
      keep,
      consumed,
      grid,
      cell,
      self: a,
      maxScaleRatio,
      maxDistanceFactor,
      maxColorDistance,
    });
    if (partner < 0) {
      continue;
    }
    const ib = keep[partner];
    if (ib === undefined) {
      continue;
    }
    consumed[a] = 1;
    consumed[partner] = 1;
    writeSplat(out, write, mergeSplats(splats, ia, ib));
    write += 1;
    merged += 1;
  }

  // 4. Copia o que sobrou (sem parceiro) preservando a ordem original.
  for (let a = 0; a < kept; a += 1) {
    if (consumed[a]) {
      continue;
    }
    const i = keep[a];
    if (i === undefined) {
      continue;
    }
    writeSplat(out, write, readSplat(splats, i));
    write += 1;
  }

  return {
    centers: out.centers,
    scales: out.scales,
    quaternions: out.quaternions,
    opacities: out.opacities,
    colors: out.colors,
    count: write,
    removedByOpacity,
    merged,
  };
}

/* ------------------------------------------------------------------ *
 * Internos
 * ------------------------------------------------------------------ */

interface SingleSplat {
  cx: number;
  cy: number;
  cz: number;
  sx: number;
  sy: number;
  sz: number;
  qx: number;
  qy: number;
  qz: number;
  qw: number;
  opacity: number;
  r: number;
  g: number;
  b: number;
}

/**
 * Leitura indexada que satisfaz `noUncheckedIndexedAccess`.
 *
 * Todos os acessos aqui são feitos com índices já validados (loops de
 * 0 a length-1), então o fallback 0 nunca é atingido na prática — existe
 * só para o compilador.
 */
function at(arr: Float32Array, i: number): number {
  return arr[i] ?? 0;
}

function readSplat(s: SplatArrays, i: number): SingleSplat {
  const c = i * 3;
  const q = i * 4;
  return {
    cx: at(s.centers, c),
    cy: at(s.centers, c + 1),
    cz: at(s.centers, c + 2),
    sx: at(s.scales, c),
    sy: at(s.scales, c + 1),
    sz: at(s.scales, c + 2),
    qx: at(s.quaternions, q),
    qy: at(s.quaternions, q + 1),
    qz: at(s.quaternions, q + 2),
    qw: at(s.quaternions, q + 3),
    opacity: at(s.opacities, i),
    r: at(s.colors, c),
    g: at(s.colors, c + 1),
    b: at(s.colors, c + 2),
  };
}

function writeSplat(out: SplatArrays, index: number, v: SingleSplat): void {
  const c = index * 3;
  const q = index * 4;
  out.centers[c] = v.cx;
  out.centers[c + 1] = v.cy;
  out.centers[c + 2] = v.cz;
  out.scales[c] = v.sx;
  out.scales[c + 1] = v.sy;
  out.scales[c + 2] = v.sz;
  out.quaternions[q] = v.qx;
  out.quaternions[q + 1] = v.qy;
  out.quaternions[q + 2] = v.qz;
  out.quaternions[q + 3] = v.qw;
  out.opacities[index] = v.opacity;
  out.colors[c] = v.r;
  out.colors[c + 1] = v.g;
  out.colors[c + 2] = v.b;
}

/**
 * Merge de duas gaussianas:
 * - centro e cor: média ponderada por opacidade (quem é mais opaco manda mais);
 * - escala: combinação em quadratura das variâncias (soma das gaussianas
 *   normalizadas aproxima-se de uma gaussiana mais larga);
 * - opacidade: união probabilística `1-(1-a₁)(1-a₂)` — nunca passa de 1;
 * - rotação: a do splat mais opaco (a média de quaternions deformaria a
 *   orientação quando os dois divergem muito, e o teste de escala já garante
 *   que são parecidos).
 */
export function mergeSplats(s: SplatArrays, ia: number, ib: number): SingleSplat {
  const a = readSplat(s, ia);
  const b = readSplat(s, ib);
  const wa = Math.max(a.opacity, 1e-6);
  const wb = Math.max(b.opacity, 1e-6);
  const total = wa + wb;
  const ta = wa / total;
  const tb = wb / total;

  const opacity = 1 - (1 - a.opacity) * (1 - b.opacity);
  const dominant = a.opacity >= b.opacity ? a : b;

  return {
    cx: a.cx * ta + b.cx * tb,
    cy: a.cy * ta + b.cy * tb,
    cz: a.cz * ta + b.cz * tb,
    sx: Math.sqrt(a.sx * a.sx + b.sx * b.sx),
    sy: Math.sqrt(a.sy * a.sy + b.sy * b.sy),
    sz: Math.sqrt(a.sz * a.sz + b.sz * b.sz),
    qx: dominant.qx,
    qy: dominant.qy,
    qz: dominant.qz,
    qw: dominant.qw,
    opacity,
    r: a.r * ta + b.r * tb,
    g: a.g * ta + b.g * tb,
    b: a.b * ta + b.b * tb,
  };
}

function estimateCellSize(s: SplatArrays, keep: Uint32Array, kept: number): number {
  // Amostra até 4096 splats para não pagar O(n log n) da mediana cheia.
  const step = Math.max(1, Math.floor(kept / 4096));
  const samples: number[] = [];
  for (let a = 0; a < kept; a += step) {
    const i = keep[a];
    if (i === undefined) {
      continue;
    }
    const c = i * 3;
    samples.push(
      (Math.abs(at(s.scales, c)) + Math.abs(at(s.scales, c + 1)) + Math.abs(at(s.scales, c + 2))) /
        3,
    );
  }
  if (samples.length === 0) {
    return 1;
  }
  samples.sort((x, y) => x - y);
  const median = samples[Math.floor(samples.length / 2)] ?? 0;
  return median > 1e-6 ? median * 2 : 1e-3;
}

interface Grid {
  cell: number;
  /** Mapa "ix,iy,iz" → índices em `keep`. */
  buckets: Map<string, number[]>;
}

function buildGrid(s: SplatArrays, keep: Uint32Array, kept: number, cell: number): Grid {
  const buckets = new Map<string, number[]>();
  for (let a = 0; a < kept; a += 1) {
    const i = keep[a];
    if (i === undefined) {
      continue;
    }
    const c = i * 3;
    const key = cellKey(at(s.centers, c), at(s.centers, c + 1), at(s.centers, c + 2), cell);
    const bucket = buckets.get(key);
    if (bucket) {
      bucket.push(a);
    } else {
      buckets.set(key, [a]);
    }
  }
  return { cell, buckets };
}

function cellKey(x: number, y: number, z: number, cell: number): string {
  return `${Math.floor(x / cell)},${Math.floor(y / cell)},${Math.floor(z / cell)}`;
}

interface FindPartnerArgs {
  splats: SplatArrays;
  keep: Uint32Array;
  consumed: Uint8Array;
  grid: Grid;
  cell: number;
  self: number;
  maxScaleRatio: number;
  maxDistanceFactor: number;
  maxColorDistance: number;
}

/** Procura o melhor vizinho para merge nas 27 células ao redor. */
function findMergePartner(args: FindPartnerArgs): number {
  const { splats, keep, consumed, grid, cell, self } = args;
  const ia = keep[self];
  if (ia === undefined) {
    return -1;
  }
  const ca = ia * 3;
  const ax = at(splats.centers, ca);
  const ay = at(splats.centers, ca + 1);
  const az = at(splats.centers, ca + 2);
  const asx = Math.abs(at(splats.scales, ca));
  const asy = Math.abs(at(splats.scales, ca + 1));
  const asz = Math.abs(at(splats.scales, ca + 2));
  const ar = at(splats.colors, ca);
  const ag = at(splats.colors, ca + 1);
  const ab = at(splats.colors, ca + 2);

  const bx = Math.floor(ax / cell);
  const by = Math.floor(ay / cell);
  const bz = Math.floor(az / cell);

  let best = -1;
  let bestCost = Number.POSITIVE_INFINITY;

  for (let dx = -1; dx <= 1; dx += 1) {
    for (let dy = -1; dy <= 1; dy += 1) {
      for (let dz = -1; dz <= 1; dz += 1) {
        const bucket = grid.buckets.get(
          `${bx + dx},${by + dy},${bz + dz}`,
        );
        if (!bucket) {
          continue;
        }
        for (const candidate of bucket) {
          if (candidate === self || consumed[candidate]) {
            continue;
          }
          const ib = keep[candidate];
          if (ib === undefined) {
            continue;
          }
          const cb = ib * 3;
          const bsx = Math.abs(at(splats.scales, cb));
          const bsy = Math.abs(at(splats.scales, cb + 1));
          const bsz = Math.abs(at(splats.scales, cb + 2));

          // Teste 1: escalas compatíveis.
          const ratio = Math.max(
            ratioOrInfinity(asx, bsx),
            ratioOrInfinity(asy, bsy),
            ratioOrInfinity(asz, bsz),
          );
          if (ratio > args.maxScaleRatio) {
            continue;
          }

          // Teste 2: centros dentro do raio aceitável.
          const dxc = at(splats.centers, cb) - ax;
          const dyc = at(splats.centers, cb + 1) - ay;
          const dzc = at(splats.centers, cb + 2) - az;
          const dist = Math.sqrt(dxc * dxc + dyc * dyc + dzc * dzc);
          const meanScale = (asx + asy + asz + bsx + bsy + bsz) / 6;
          if (dist > args.maxDistanceFactor * meanScale) {
            continue;
          }

          // Teste 3: cores parecidas (não mistura materiais).
          const dr = at(splats.colors, cb) - ar;
          const dg = at(splats.colors, cb + 1) - ag;
          const db = at(splats.colors, cb + 2) - ab;
          const colorDist = Math.sqrt(dr * dr + dg * dg + db * db);
          if (colorDist > args.maxColorDistance) {
            continue;
          }

          // Custo: prefere o par mais próximo e mais parecido.
          const cost = dist / Math.max(meanScale, 1e-9) + colorDist;
          if (cost < bestCost) {
            bestCost = cost;
            best = candidate;
          }
        }
      }
    }
  }

  return best;
}

function ratioOrInfinity(a: number, b: number): number {
  const lo = Math.min(Math.abs(a), Math.abs(b));
  const hi = Math.max(Math.abs(a), Math.abs(b));
  if (lo < 1e-9) {
    // Um dos dois é degenerado (achatado): só aceita se ambos forem.
    return hi < 1e-9 ? 1 : Number.POSITIVE_INFINITY;
  }
  return hi / lo;
}

function allocate(count: number): SplatArrays {
  return {
    centers: new Float32Array(count * 3),
    scales: new Float32Array(count * 3),
    quaternions: new Float32Array(count * 4),
    opacities: new Float32Array(count),
    colors: new Float32Array(count * 3),
  };
}

function passthrough(
  splats: SplatArrays,
  count: number,
  removedByOpacity = 0,
): DecimateResult {
  return {
    centers: splats.centers,
    scales: splats.scales,
    quaternions: splats.quaternions,
    opacities: splats.opacities,
    colors: splats.colors,
    count,
    removedByOpacity,
    merged: 0,
  };
}

function emptyResult(originalCount: number): DecimateResult {
  const out = allocate(Math.max(1, originalCount));
  return { ...out, count: 0, removedByOpacity: originalCount, merged: 0 };
}
