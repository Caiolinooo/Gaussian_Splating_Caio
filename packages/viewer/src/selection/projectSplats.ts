/**
 * Projeção de centros de splats para screen space.
 *
 * Módulo PURO: não depende de `three`, DOM ou WebGL — apenas aritmética sobre
 * uma matriz viewProjection column-major (16 componentes, igual ao layout de
 * `THREE.Matrix4.elements` / `Float32Array` do WebGL).
 *
 * Origem de `px/py`: topo-esquerdo (y cresce para baixo), como o canvas.
 */

/** Tamanho do viewport em pixels. */
export interface ViewportSize {
  width: number;
  height: number;
}

/** Centro de um splat após projeção. */
export interface ProjectedPoint {
  /** Coordenada normalizada X em [-1, 1]. */
  ndcX: number;
  /** Coordenada normalizada Y em [-1, 1]. */
  ndcY: number;
  /** Profundidade normalizada em [-1, 1] (OpenGL) — fora da faixa = fora do frustum. */
  ndcZ: number;
  /** Pixel X (origem topo-esquerdo). */
  px: number;
  /** Pixel Y (origem topo-esquerdo, cresce para baixo). */
  py: number;
  /** `true` apenas se o ponto está dentro do frustum (w > 0 e NDC nos limites). */
  visible: boolean;
}

/**
 * Lê um componente da matriz validando presença.
 * Matrizes truncatedas são erro de programação — falhamos cedo e em pt-BR.
 */
function readComponent(m: ArrayLike<number>, index: number): number {
  const value = m[index];
  if (value === undefined) {
    throw new Error(
      `Matriz viewProjection incompleta: componente ${index} ausente (esperado 16).`,
    );
  }
  return value;
}

/**
 *Projeta um centro (x, y, z) usando a matriz viewProjection `m` (column-major).
 *
 * - `w <= 0` → ponto atrás da câmera: `visible = false` e NDC/px zerados.
 * - Visibilidade também exige `ndcX`, `ndcY` e `ndcZ` em [-1, 1].
 *
 * @param cx coordenada X do centro em espaço de mundo.
 * @param cy coordenada Y do centro em espaço de mundo.
 * @param cz coordenada Z do centro em espaço de mundo.
 * @param m viewProjection column-major com 16 componentes.
 * @param viewport largura/altura em pixels.
 */
export function projectCenter(
  cx: number,
  cy: number,
  cz: number,
  m: ArrayLike<number>,
  viewport: ViewportSize,
): ProjectedPoint {
  // Cache local: evita 16 leituras validadas por splat dentro do laço quente.
  const m0 = readComponent(m, 0);
  const m1 = readComponent(m, 1);
  const m2 = readComponent(m, 2);
  const m3 = readComponent(m, 3);
  const m4 = readComponent(m, 4);
  const m5 = readComponent(m, 5);
  const m6 = readComponent(m, 6);
  const m7 = readComponent(m, 7);
  const m8 = readComponent(m, 8);
  const m9 = readComponent(m, 9);
  const m10 = readComponent(m, 10);
  const m11 = readComponent(m, 11);
  const m12 = readComponent(m, 12);
  const m13 = readComponent(m, 13);
  const m14 = readComponent(m, 14);
  const m15 = readComponent(m, 15);

  const w = m3 * cx + m7 * cy + m11 * cz + m15;
  if (w <= 0) {
    // Atrás (ou sobre) o plano da câmera: sem divisão segura, nada a desenhar.
    return { ndcX: 0, ndcY: 0, ndcZ: 0, px: 0, py: 0, visible: false };
  }

  const invW = 1 / w;
  const ndcX = (m0 * cx + m4 * cy + m8 * cz + m12) * invW;
  const ndcY = (m1 * cx + m5 * cy + m9 * cz + m13) * invW;
  const ndcZ = (m2 * cx + m6 * cy + m10 * cz + m14) * invW;

  const px = (ndcX * 0.5 + 0.5) * viewport.width;
  const py = (1 - (ndcY * 0.5 + 0.5)) * viewport.height;

  const visible =
    ndcX >= -1 && ndcX <= 1 && ndcY >= -1 && ndcY <= 1 && ndcZ >= -1 && ndcZ <= 1;

  return { ndcX, ndcY, ndcZ, px, py, visible };
}

/**
 * Projeta uma nuvem de centros intercalados (xyz, xyz, ...) e devolve
 * apenas os índices cujo centro é visível em tela.
 *
 * Conveniência para o backend: evita replicar o laço em cada operação
 * de retângulo/laço.
 *
 * @param centers buffer com centros intercalados (3 floats por splat).
 * @param m viewProjection column-major com 16 componentes.
 * @param viewport largura/altura em pixels.
 * @param onProjected callback por splat projetado (recebe índice e ponto).
 */
export function forEachProjectedCenter(
  centers: Float32Array,
  m: ArrayLike<number>,
  viewport: ViewportSize,
  onProjected: (index: number, point: ProjectedPoint) => void,
): void {
  const count = Math.floor(centers.length / 3);
  for (let i = 0; i < count; i += 1) {
    const base = i * 3;
    const cx = centers[base];
    const cy = centers[base + 1];
    const cz = centers[base + 2];
    if (cx === undefined || cy === undefined || cz === undefined) {
      continue; // buffer truncado: ignora a sobra
    }
    onProjected(i, projectCenter(cx, cy, cz, m, viewport));
  }
}
