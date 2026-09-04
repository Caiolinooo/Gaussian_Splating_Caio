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
 */
export interface SplatQuality {
  shDegree: SphericalHarmonicsDegree;
  alphaRemovalThreshold: number;
}

export const DEFAULT_SPLAT_QUALITY: SplatQuality = Object.freeze({
  shDegree: 1,
  alphaRemovalThreshold: 1,
});

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

/**
 * Contrato único do renderer de splats.
 * Spark (primário) e @mkkellogg/gaussian-splats-3d (fallback) implementam esta interface.
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

  /** Reprodução temporal (Fase 6). No MVP só altera o flag interno. */
  play(): void;

  pause(): void;

  isPlaying(): boolean;

  /** Contagem de gaussianas (de um splat ou soma de todos). */
  getGaussianCount(handle?: SplatHandle): number;

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
