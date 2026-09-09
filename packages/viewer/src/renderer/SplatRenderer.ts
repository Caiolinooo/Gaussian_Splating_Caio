import type { TRS } from '../math/trs';
import type { Vec3 } from '../math/vec3';

/** Formatos de splat suportados pelo contrato (master + web). */
export type SplatFormat = 'ply' | 'ksplat';

/** Backend concreto atrás de `SplatRenderer`. */
export type RendererBackendKind = 'spark' | 'mkkellogg';

/** Grau de spherical harmonics. Spark até 3; MkKellogg até 2. */
export type SphericalHarmonicsDegree = 0 | 1 | 2 | 3;

/**
 * Identificador opaco de um splat carregado.
 * Não vaze o mesh/nativo do backend para o app.
 */
export interface SplatHandle {
  readonly id: string;
}

/** Fonte de carregamento: URL remota/local ou buffer em memória. */
export interface SplatLoadSource {
  readonly url?: string;
  readonly buffer?: ArrayBuffer | Uint8Array;
  readonly format: SplatFormat;
}

export interface SplatLoadProgress {
  readonly loaded: number;
  readonly total: number;
  readonly ratio: number;
}

export interface SplatLoadOptions {
  onProgress?: (progress: SplatLoadProgress) => void;
  quality?: Partial<SplatQuality>;
  trs?: TRS;
  name?: string;
}

/**
 * Qualidade de rasterização compartilhada pelos backends.
 * `alphaRemovalThreshold` segue a escala MkKellogg (0–255).
 *
 * Os campos anti-smearing (`blurAmount`, `preBlurAmount`, `focalAdjustment`,
 * `maxStdDev`, `clipXY`, `falloff`) espelham as knobs homônimas do
 * `SparkRenderer`. São ignorados pelo MkKellogg (não expõe equivalentes).
 */
export interface SplatQuality {
  shDegree: SphericalHarmonicsDegree;
  alphaRemovalThreshold: number;
  /**
   * Soma à diagonal da covariância 2D — "blur" de cada gaussiana em px².
   * 0.3 é o default do Spark e o correto para cenas treinadas SEM o tweak de
   * anti-aliasing; **0.0 é o correto para cenas treinadas com anti-aliasing**.
   * É a causa nº 1 de smearing: infla cada splat em ~0.5px de raio.
   */
  blurAmount: number;
  /** Idem `blurAmount`, aplicado antes da decomposição de covariância. */
  preBlurAmount: number;
  /**
   * Escala o tamanho projetado do splat. 1.0 = comportamento legado;
   * 2.0 reproduz o PlayCanvas/SuperSplat (mais nítido).
   */
  focalAdjustment: number;
  /** Desvios-padrão máximos renderizados. √8≈2.83 (default Spark) tem caudas
   *  longas; SuperSplat fica perto de √5≈2.24. Encurtar reduz streaks. */
  maxStdDev: number;
  /** Fator de clip XY no frustum (1.0 = exato, 1.4 = 40% além). */
  clipXY: number;
  /** Modula o decaimento do kernel: 1 = gaussiana normal, 0 = chapado. */
  falloff: number;
  /** Sort radial (geométrico, estável sob rotação) vs. por Z-depth. */
  sortRadial: boolean;
  /** Raio mínimo em px para um splat ser desenhado. */
  minPixelRadius: number;
  /** Intervalo mínimo entre sorts (ms). 0 = sortar todo frame. */
  minSortIntervalMs: number;
}

export const DEFAULT_SPLAT_QUALITY: SplatQuality = Object.freeze({
  shDegree: 3,
  alphaRemovalThreshold: 1,
  // Anti-smearing: ver docs/plan-editorsplat.md §2.
  blurAmount: 0,
  preBlurAmount: 0,
  focalAdjustment: 2,
  maxStdDev: Math.sqrt(5),
  clipXY: 1.4,
  falloff: 1,
  sortRadial: true,
  minPixelRadius: 0,
  minSortIntervalMs: 0,
});

/** Limites seguros para a UI (evita valores que quebram o shader). */
export const SPLAT_QUALITY_RANGE = Object.freeze({
  blurAmount: { min: 0, max: 1, step: 0.01 },
  preBlurAmount: { min: 0, max: 1, step: 0.01 },
  focalAdjustment: { min: 0.5, max: 3, step: 0.05 },
  maxStdDev: { min: 1, max: 4, step: 0.05 },
  clipXY: { min: 1, max: 2, step: 0.05 },
  falloff: { min: 0, max: 1, step: 0.01 },
  minPixelRadius: { min: 0, max: 4, step: 0.05 },
  minSortIntervalMs: { min: 0, max: 200, step: 1 },
});

export function clampQualityNumber(
  key: keyof typeof SPLAT_QUALITY_RANGE,
  value: number,
): number {
  const range = SPLAT_QUALITY_RANGE[key];
  if (!Number.isFinite(value)) {
    return DEFAULT_SPLAT_QUALITY[key];
  }
  return Math.max(range.min, Math.min(range.max, value));
}

/** AABB em espaço de mundo para enquadrar a câmera no splat. */
export interface WorldBox {
  min: Vec3;
  max: Vec3;
}

export interface SplatPickOptions {
  /** Distância máxima do raio ao centro/hit (unidades de cena). */
  maxDistance?: number;
  /** Opacidade mínima para considerar uma gaussiana (0–1). */
  minOpacity?: number;
}

export interface SplatPickHit {
  handle: SplatHandle;
  distance: number;
  point: Vec3;
  splatIndex?: number;
}

export interface SplatCapabilities {
  backend: RendererBackendKind;
  webgpu: boolean;
  webgl2: boolean;
  maxShDegree: SphericalHarmonicsDegree;
  supportsDynamicEdits: boolean;
  supportsProgressiveLoad: boolean;
  supportsNativeSplatRaycast: boolean;
  /** Texto para badge na UI (pt-BR). */
  selectionReason: string;
  selectionReasonCode: BackendReasonCode;
}

export type BackendReasonCode =
  'webgpu' | 'webgl2-fallback' | 'spark-webgl2' | 'forced' | 'unsupported';

/**
 * Pai de cena mínimo (THREE.Object3D / Scene satisfazem).
 * Evita acoplar o contrato a tipos de `three` no núcleo testável.
 */
export interface SceneParent {
  add(object: unknown): unknown;
  remove?(object: unknown): unknown;
}

/** Raio em espaço de mundo para picking. */
export interface Ray3 {
  origin: Vec3;
  /** Deve ser normalizado pelos callers quando possível. */
  direction: Vec3;
}

/* ------------------------------------------------------------------ *
 * Seleção e edição de splats (C1).
 * ------------------------------------------------------------------ */

/** Região retangular em pixels de tela (origem topo-esquerdo). */
export interface ScreenRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Modo de composição da seleção. */
export type SelectMode = 'replace' | 'add' | 'subtract' | 'intersect';

/** Conjunto de splats selecionados (índices no splat do handle). */
export interface SplatSelection {
  readonly handle: SplatHandle;
  readonly indices: Uint32Array;
  readonly count: number;
}

/** Ajustes visuais aplicáveis a uma seleção. */
export interface AppearanceParams {
  brightness?: number;
  saturation?: number;
  temperature?: number;
  opacity?: number;
  /** Cor sólida (RGB 0–1) — usada por `SET_RGB`. */
  color?: [number, number, number];
}

/** Acesso aos dados brutos de um splat (para export/decimação). */
export interface SplatDataAccessor {
  readonly count: number;
  centers: Float32Array;
  scales: Float32Array;
  quaternions: Float32Array;
  opacities: Float32Array;
  colors: Float32Array;
}

/** Forma 3D usada nas operações de corte/recorte. */
export type RegionShape =
  | { type: 'sphere'; center: Vec3; radius: number }
  | { type: 'box'; center: Vec3; size: Vec3; rotation?: QuatLike }
  | { type: 'plane'; point: Vec3; normal: Vec3 };

export interface QuatLike {
  x: number;
  y: number;
  z: number;
  w: number;
}

/**
 * Contrato único do renderer de splats.
 * Spark (primário) e @mkkellogg/gaussian-splats-3d (fallback) implementam esta interface.
 *
 * Os métodos marcados com `?` são capacidades opcionais: hoje só o Spark
 * implementa edição de splats. A UI degrada escondendo o que falta.
 */
export interface SplatRenderer {
  readonly kind: RendererBackendKind;
  readonly capabilities: SplatCapabilities;

  /**
   * Carrega um splat `.ply` ou `.ksplat` a partir de URL ou buffer.
   * Não adiciona à cena — use `addToScene`.
   */
  load(source: SplatLoadSource, options?: SplatLoadOptions): Promise<SplatHandle>;

  /** Anexa o splat a uma `THREE.Scene` (ou Object3D pai) hospedeira. */
  addToScene(handle: SplatHandle, parent: SceneParent): void;

  /** Remove o splat da cena hospedeira sem liberar GPU (use `dispose` para isso). */
  removeFromScene(handle: SplatHandle): void;

  /** Define TRS por splat (múltiplas cenas / objetos splat). */
  setTRS(handle: SplatHandle, trs: TRS): void;

  getTRS(handle: SplatHandle): TRS;

  /**
   * Picking: raio → gaussiana/objeto mais próximo.
   * Backends nativos usam raycast próprio; fallback aproxima pelo centro.
   */
  pick(ray: Ray3, options?: SplatPickOptions): SplatPickHit | null;

  /** Ajusta SH degree e limiar de alpha (efeito imediato quando o backend permitir). */
  setQuality(quality: Partial<SplatQuality>): void;

  getQuality(): SplatQuality;

  /** Reprodução temporal 0–1 (scrubber 4D / câmeras COLMAP). */
  play(): void;

  pause(): void;

  isPlaying(): boolean;

  /** Tempo normalizado 0–1. Spark aplica offset de clusters via TRS no controller. */
  setTime(normalized: number): void;

  getTime(): number;

  /** Relight SH-env: `recolor` no Spark + estado no fallback WebGL2. */
  setRelightEnabled(enabled: boolean): void;

  setRelight(params: {
    enabled: boolean;
    azimuthDeg: number;
    elevationDeg: number;
    intensity: number;
  }): void;

  isRelightEnabled(): boolean;

  /** Contagem de gaussianas (de um splat ou soma de todos). */
  getGaussianCount(handle?: SplatHandle): number;

  /** AABB em mundo do splat (ou do primeiro carregado). Null se ainda vazio. */
  getWorldBounds(handle?: SplatHandle): WorldBox | null;

  /* --- Seleção e edição (C1) — opcionais, só Spark por ora --- */

  /** Seleciona splats cujo centro projetado cai no retângulo de tela. */
  selectByRect?(
    handle: SplatHandle,
    rect: ScreenRect,
    viewProjection: ArrayLike<number>,
    viewport: { width: number; height: number },
    mode: SelectMode,
  ): SplatSelection;

  /** Seleciona splats cujo centro projetado cai dentro do polígono (lasso). */
  selectByLasso?(
    handle: SplatHandle,
    points: { x: number; y: number }[],
    viewProjection: ArrayLike<number>,
    viewport: { width: number; height: number },
    mode: SelectMode,
  ): SplatSelection;

  /** Seleciona splats dentro de uma região 3D. */
  selectByRegion?(
    handle: SplatHandle,
    shape: RegionShape,
    mode: SelectMode,
  ): SplatSelection;

  /** Remove splats selecionados (limpeza de floaters). */
  deleteSplats?(selection: SplatSelection): void;

  /** Ajustes visuais por seleção (brightness/saturation/temperature/opacity). */
  adjustAppearance?(selection: SplatSelection, params: AppearanceParams): void;

  /** Mantém apenas o que está dentro da região (corta o resto). */
  cropToRegion?(handle: SplatHandle, shape: RegionShape, invert?: boolean): void;

  /** Decimação: merge de gaussianas similares até ~`target`. */
  decimateSplats?(handle: SplatHandle, target: number): Promise<number>;

  /** Snapshot dos dados brutos (para export e decimação). */
  getSplatData?(handle: SplatHandle): SplatDataAccessor | null;

  /** Libera GPU, workers e object URLs. */
  dispose(): void;
}

export function mergeQuality(
  current: SplatQuality,
  patch: Partial<SplatQuality>,
  maxSh: SphericalHarmonicsDegree,
): SplatQuality {
  const rawDegree = patch.shDegree ?? current.shDegree;
  const clamped = Math.max(0, Math.min(maxSh, Math.round(rawDegree)));
  const shDegree = toShDegree(clamped);
  const alpha = patch.alphaRemovalThreshold ?? current.alphaRemovalThreshold;
  return {
    shDegree,
    alphaRemovalThreshold: Math.max(0, Math.min(255, alpha)),
    blurAmount: clampQualityNumber('blurAmount', patch.blurAmount ?? current.blurAmount),
    preBlurAmount: clampQualityNumber(
      'preBlurAmount',
      patch.preBlurAmount ?? current.preBlurAmount,
    ),
    focalAdjustment: clampQualityNumber(
      'focalAdjustment',
      patch.focalAdjustment ?? current.focalAdjustment,
    ),
    maxStdDev: clampQualityNumber('maxStdDev', patch.maxStdDev ?? current.maxStdDev),
    clipXY: clampQualityNumber('clipXY', patch.clipXY ?? current.clipXY),
    falloff: clampQualityNumber('falloff', patch.falloff ?? current.falloff),
    sortRadial: patch.sortRadial ?? current.sortRadial,
    minPixelRadius: clampQualityNumber(
      'minPixelRadius',
      patch.minPixelRadius ?? current.minPixelRadius,
    ),
    minSortIntervalMs: clampQualityNumber(
      'minSortIntervalMs',
      patch.minSortIntervalMs ?? current.minSortIntervalMs,
    ),
  };
}

export function toShDegree(value: number): SphericalHarmonicsDegree {
  switch (value) {
    case 0:
      return 0;
    case 1:
      return 1;
    case 2:
      return 2;
    case 3:
      return 3;
    default:
      throw new Error(`Grau de SH inválido: ${value}`);
  }
}

export function assertSplatFormat(format: SplatFormat): void {
  switch (format) {
    case 'ply':
    case 'ksplat':
      return;
    default: {
      const exhaustive: never = format;
      throw new Error(`Formato de splat não suportado: ${String(exhaustive)}`);
    }
  }
}

export function resolveLoadUrl(source: SplatLoadSource, objectUrls: string[]): string {
  assertSplatFormat(source.format);
  if (source.url) {
    return source.url;
  }
  if (source.buffer) {
    const bytes =
      source.buffer instanceof Uint8Array ? source.buffer : new Uint8Array(source.buffer);
    const blob = new Blob([bytes as BlobPart], { type: 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    objectUrls.push(url);
    return url;
  }
  throw new Error('SplatLoadSource requer `url` ou `buffer`.');
}
