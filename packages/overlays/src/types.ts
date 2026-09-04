import { assertNever } from './assertNever';

/** Versão do schema persistido no JSON de cena. Incrementar em breaking changes. */
export const OVERLAY_SCHEMA_VERSION = 1 as const;

export type OverlaySchemaVersion = typeof OVERLAY_SCHEMA_VERSION;

/** Unidades alinhadas ao núcleo `@gs/units` (sem importar esse pacote). */
export const LENGTH_UNITS = ['mm', 'cm', 'm', 'in', 'ft'] as const;
export type LengthUnit = (typeof LENGTH_UNITS)[number];

export type OverlayKind = 'paint' | 'wallpaper' | 'sticker';

export type BlendMode = 'normal' | 'multiply' | 'overlay';

/** Vetor 3D serializável (JSON de cena). */
export interface Vec3Tuple {
  x: number;
  y: number;
  z: number;
}

/**
 * Pose do projetor virtual (caixa de projeção centrada na superfície).
 * `scale.x/y` = extensão da projeção em unidades de cena (exceto sticker,
 * cujo frustum vem de `physicalSize`). `scale.z` = profundidade da caixa.
 * Rotação em radianos, ordem Euler XYZ. Eixo local −Z é a direção de projeção.
 */
export interface OverlayTransform {
  position: Vec3Tuple;
  rotation: Vec3Tuple;
  scale: Vec3Tuple;
}

/** Repeat/offset UV explícito (override do cálculo físico). */
export interface Tiling {
  repeatU: number;
  repeatV: number;
  offsetU?: number;
  offsetV?: number;
}

/** Comprimento com unidade real (cm/mm/m/in/ft). */
export interface PhysicalLength {
  value: number;
  unit: LengthUnit;
}

/**
 * Dimensão exata em unidade real.
 * - sticker: tamanho do adesivo (ex.: 30 × 45 cm).
 * - wallpaper: tamanho de um tile da estampa (ex.: 10 × 10 cm).
 * - paint: região pintada, se informada; senão usa `transform.scale`.
 */
export interface PhysicalSize {
  width: PhysicalLength;
  height: PhysicalLength;
}

/**
 * Recorte anti-sangramento em quinas.
 * `threshold` é cos(ângulo máximo): a fragmento com N·(−D) < threshold é descartado.
 * Padrão 0,5 ≈ 60°.
 */
export interface MaskByNormal {
  enabled: boolean;
  threshold: number;
}

interface OverlayBase {
  id: string;
  opacity: number;
  blendMode: BlendMode;
  transform: OverlayTransform;
  /** Nome/`userData.id` da malha proxy-alvo. Sem valor: todas as malhas do proxy. */
  targetSurface?: string;
  maskByNormal: MaskByNormal;
}

/** Pintura sólida (cor) com blending sobre a malha proxy. */
export interface PaintOverlay extends OverlayBase {
  kind: 'paint';
  color: string;
  textureRef?: string;
  tiling?: Tiling;
  physicalSize?: PhysicalSize;
}

/**
 * Papel de parede: textura tileada.
 * Informe `tiling` (repeat explícito) **ou** `physicalSize` (tamanho do padrão
 * em unidade real; o repeat é derivado da extensão do projetor).
 */
export interface WallpaperOverlay extends OverlayBase {
  kind: 'wallpaper';
  textureRef: string;
  color?: string;
  tiling?: Tiling;
  physicalSize?: PhysicalSize;
}

/** Adesivo com alpha e dimensão exata obrigatória. */
export interface StickerOverlay extends OverlayBase {
  kind: 'sticker';
  textureRef: string;
  color?: string;
  physicalSize: PhysicalSize;
  tiling?: Tiling;
}

export type Overlay = PaintOverlay | WallpaperOverlay | StickerOverlay;

/** Documento versionado embutido no JSON de cena. */
export interface OverlayDocument {
  schemaVersion: OverlaySchemaVersion;
  overlays: Overlay[];
}

/** Entrada de criação (id opcional). */
export type OverlayDraft =
  | (Omit<PaintOverlay, 'id' | 'opacity' | 'blendMode' | 'transform' | 'maskByNormal'> & {
      kind: 'paint';
      id?: string;
      opacity?: number;
      blendMode?: BlendMode;
      transform?: Partial<OverlayTransform>;
      maskByNormal?: Partial<MaskByNormal>;
    })
  | (Omit<WallpaperOverlay, 'id' | 'opacity' | 'blendMode' | 'transform' | 'maskByNormal'> & {
      kind: 'wallpaper';
      id?: string;
      opacity?: number;
      blendMode?: BlendMode;
      transform?: Partial<OverlayTransform>;
      maskByNormal?: Partial<MaskByNormal>;
    })
  | (Omit<StickerOverlay, 'id' | 'opacity' | 'blendMode' | 'transform' | 'maskByNormal'> & {
      kind: 'sticker';
      id?: string;
      opacity?: number;
      blendMode?: BlendMode;
      transform?: Partial<OverlayTransform>;
      maskByNormal?: Partial<MaskByNormal>;
    });

/** Patch parcial para preview/update (deep-merge nos aninhados). */
export type OverlayPatch = {
  kind?: OverlayKind;
  textureRef?: string;
  color?: string;
  opacity?: number;
  blendMode?: BlendMode;
  transform?: Partial<OverlayTransform> & {
    position?: Partial<Vec3Tuple>;
    rotation?: Partial<Vec3Tuple>;
    scale?: Partial<Vec3Tuple>;
  };
  tiling?: Tiling;
  physicalSize?: PhysicalSize;
  targetSurface?: string | undefined;
  maskByNormal?: Partial<MaskByNormal>;
};

export const DEFAULT_NORMAL_THRESHOLD = 0.5;

/** Transformação identidade: caixa 1×1×0,5 (unidades de cena). */
export function defaultTransform(): OverlayTransform {
  return {
    position: { x: 0, y: 0, z: 0 },
    rotation: { x: 0, y: 0, z: 0 },
    scale: { x: 1, y: 1, z: 0.5 },
  };
}

/** Máscara por normal ligada, 60° (cos = 0,5). */
export function defaultMaskByNormal(): MaskByNormal {
  return { enabled: true, threshold: DEFAULT_NORMAL_THRESHOLD };
}

/** Índice de kind para uniform `uKind` do shader. */
export function overlayKindToIndex(kind: OverlayKind): number {
  switch (kind) {
    case 'paint':
      return 0;
    case 'wallpaper':
      return 1;
    case 'sticker':
      return 2;
    default:
      return assertNever(kind, `Unknown overlay kind: ${String(kind)}`);
  }
}

/** Índice de blend para uniform `uBlendMode` do shader. */
export function blendModeToIndex(mode: BlendMode): number {
  switch (mode) {
    case 'normal':
      return 0;
    case 'multiply':
      return 1;
    case 'overlay':
      return 2;
    default:
      return assertNever(mode, `Unknown blend mode: ${String(mode)}`);
  }
}

/** Rótulo estável para UI/HUD. */
export function overlayKindLabel(kind: OverlayKind): string {
  switch (kind) {
    case 'paint':
      return 'paint';
    case 'wallpaper':
      return 'wallpaper';
    case 'sticker':
      return 'sticker';
    default:
      return assertNever(kind);
  }
}

export function isLengthUnit(value: unknown): value is LengthUnit {
  return value === 'mm' || value === 'cm' || value === 'm' || value === 'in' || value === 'ft';
}

export function isOverlayKind(value: unknown): value is OverlayKind {
  return value === 'paint' || value === 'wallpaper' || value === 'sticker';
}

export function isBlendMode(value: unknown): value is BlendMode {
  return value === 'normal' || value === 'multiply' || value === 'overlay';
}

export function isPaintOverlay(overlay: Overlay): overlay is PaintOverlay {
  switch (overlay.kind) {
    case 'paint':
      return true;
    case 'wallpaper':
    case 'sticker':
      return false;
    default:
      return assertNever(overlay);
  }
}

export function isWallpaperOverlay(overlay: Overlay): overlay is WallpaperOverlay {
  switch (overlay.kind) {
    case 'wallpaper':
      return true;
    case 'paint':
    case 'sticker':
      return false;
    default:
      return assertNever(overlay);
  }
}

export function isStickerOverlay(overlay: Overlay): overlay is StickerOverlay {
  switch (overlay.kind) {
    case 'sticker':
      return true;
    case 'paint':
    case 'wallpaper':
      return false;
    default:
      return assertNever(overlay);
  }
}
