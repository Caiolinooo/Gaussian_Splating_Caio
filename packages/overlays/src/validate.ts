import { assertNever } from './assertNever';
import {
  defaultMaskByNormal,
  defaultTransform,
  isBlendMode,
  isLengthUnit,
  isOverlayKind,
  type BlendMode,
  type MaskByNormal,
  type Overlay,
  type OverlayDraft,
  type OverlayKind,
  type OverlayPatch,
  type OverlayTransform,
  type PhysicalLength,
  type PhysicalSize,
  type Tiling,
  type Vec3Tuple,
} from './types';

/** Erro de validação do modelo de overlay (schema / regras de negócio). */
export class OverlayValidationError extends Error {
  readonly issues: readonly string[];

  constructor(issues: string | readonly string[]) {
    const list = typeof issues === 'string' ? [issues] : [...issues];
    super(list.join('; '));
    this.name = 'OverlayValidationError';
    this.issues = list;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function readString(value: unknown, field: string, issues: string[]): string | undefined {
  if (value === undefined) {
    return undefined;
  }
  if (typeof value !== 'string' || value.length === 0) {
    issues.push(`${field} must be a non-empty string`);
    return undefined;
  }
  return value;
}

function readVec3(value: unknown, field: string, issues: string[]): Vec3Tuple | undefined {
  if (!isRecord(value)) {
    issues.push(`${field} must be {x,y,z}`);
    return undefined;
  }
  if (!isFiniteNumber(value.x) || !isFiniteNumber(value.y) || !isFiniteNumber(value.z)) {
    issues.push(`${field} components must be finite numbers`);
    return undefined;
  }
  return { x: value.x, y: value.y, z: value.z };
}

function readPhysicalLength(
  value: unknown,
  field: string,
  issues: string[],
): PhysicalLength | undefined {
  if (!isRecord(value)) {
    issues.push(`${field} must be {value, unit}`);
    return undefined;
  }
  if (!isFiniteNumber(value.value) || value.value <= 0) {
    issues.push(`${field}.value must be a finite number > 0`);
    return undefined;
  }
  if (!isLengthUnit(value.unit)) {
    issues.push(`${field}.unit must be one of mm|cm|m|in|ft`);
    return undefined;
  }
  return { value: value.value, unit: value.unit };
}

function readPhysicalSize(
  value: unknown,
  field: string,
  issues: string[],
): PhysicalSize | undefined {
  if (value === undefined) {
    return undefined;
  }
  if (!isRecord(value)) {
    issues.push(`${field} must be {width, height}`);
    return undefined;
  }
  const width = readPhysicalLength(value.width, `${field}.width`, issues);
  const height = readPhysicalLength(value.height, `${field}.height`, issues);
  if (!width || !height) {
    return undefined;
  }
  return { width, height };
}

function readTiling(value: unknown, field: string, issues: string[]): Tiling | undefined {
  if (value === undefined) {
    return undefined;
  }
  if (!isRecord(value)) {
    issues.push(`${field} must be {repeatU, repeatV}`);
    return undefined;
  }
  const tilingIssues: string[] = [];
  if (!isFiniteNumber(value.repeatU) || value.repeatU <= 0) {
    tilingIssues.push(`${field}.repeatU must be a finite number > 0`);
  }
  if (!isFiniteNumber(value.repeatV) || value.repeatV <= 0) {
    tilingIssues.push(`${field}.repeatV must be a finite number > 0`);
  }
  const offsetU = value.offsetU;
  const offsetV = value.offsetV;
  if (offsetU !== undefined && !isFiniteNumber(offsetU)) {
    tilingIssues.push(`${field}.offsetU must be a finite number`);
  }
  if (offsetV !== undefined && !isFiniteNumber(offsetV)) {
    tilingIssues.push(`${field}.offsetV must be a finite number`);
  }
  issues.push(...tilingIssues);
  if (tilingIssues.length > 0) {
    return undefined;
  }
  const tiling: Tiling = {
    repeatU: value.repeatU as number,
    repeatV: value.repeatV as number,
  };
  if (isFiniteNumber(offsetU)) {
    tiling.offsetU = offsetU;
  }
  if (isFiniteNumber(offsetV)) {
    tiling.offsetV = offsetV;
  }
  return tiling;
}

const HEX_COLOR = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;

function readColor(value: unknown, field: string, issues: string[]): string | undefined {
  if (value === undefined) {
    return undefined;
  }
  if (typeof value !== 'string' || !HEX_COLOR.test(value)) {
    issues.push(`${field} must be a hex color (#rgb, #rrggbb or #rrggbbaa)`);
    return undefined;
  }
  return value;
}

function mergeTransform(
  base: OverlayTransform,
  patch: OverlayPatch['transform'],
): OverlayTransform {
  return {
    position: { ...base.position, ...patch?.position },
    rotation: { ...base.rotation, ...patch?.rotation },
    scale: { ...base.scale, ...patch?.scale },
  };
}

function newOverlayId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `ovl_${Math.random().toString(36).slice(2, 12)}`;
}

/**
 * Valida um objeto desconhecido e devolve um `Overlay` canônico.
 * Sticker sem `physicalSize` é erro (dimensão exata obrigatória).
 */
export function validateOverlay(input: unknown): Overlay {
  const issues: string[] = [];
  if (!isRecord(input)) {
    throw new OverlayValidationError('Overlay must be an object');
  }

  const kindRaw = input.kind;
  if (!isOverlayKind(kindRaw)) {
    throw new OverlayValidationError(
      `kind must be paint|wallpaper|sticker, got ${String(kindRaw)}`,
    );
  }
  const kind: OverlayKind = kindRaw;

  const id = readString(input.id, 'id', issues) ?? '';
  if (!id) {
    issues.push('id is required');
  }

  let opacity = 1;
  if (input.opacity !== undefined) {
    if (!isFiniteNumber(input.opacity) || input.opacity < 0 || input.opacity > 1) {
      issues.push('opacity must be a finite number in [0, 1]');
    } else {
      opacity = input.opacity;
    }
  }

  let blendMode: BlendMode = 'normal';
  if (input.blendMode !== undefined) {
    if (!isBlendMode(input.blendMode)) {
      issues.push('blendMode must be normal|multiply|overlay');
    } else {
      blendMode = input.blendMode;
    }
  }

  const transformIn = input.transform;
  let transform = defaultTransform();
  if (transformIn !== undefined) {
    if (!isRecord(transformIn)) {
      issues.push('transform must be an object');
    } else {
      const position = readVec3(transformIn.position, 'transform.position', issues);
      const rotation = readVec3(transformIn.rotation, 'transform.rotation', issues);
      const scale = readVec3(transformIn.scale, 'transform.scale', issues);
      if (position && rotation && scale) {
        if (scale.x <= 0 || scale.y <= 0 || scale.z <= 0) {
          issues.push('transform.scale components must be > 0');
        }
        transform = { position, rotation, scale };
      }
    }
  }

  const maskIn = input.maskByNormal;
  let maskByNormal = defaultMaskByNormal();
  if (maskIn !== undefined) {
    if (!isRecord(maskIn)) {
      issues.push('maskByNormal must be an object');
    } else {
      if (typeof maskIn.enabled !== 'boolean') {
        issues.push('maskByNormal.enabled must be a boolean');
      }
      if (!isFiniteNumber(maskIn.threshold) || maskIn.threshold < -1 || maskIn.threshold > 1) {
        issues.push('maskByNormal.threshold must be a finite cosine in [-1, 1]');
      }
      if (typeof maskIn.enabled === 'boolean' && isFiniteNumber(maskIn.threshold)) {
        maskByNormal = { enabled: maskIn.enabled, threshold: maskIn.threshold };
      }
    }
  }

  const targetSurface = readString(input.targetSurface, 'targetSurface', issues);
  const tiling = readTiling(input.tiling, 'tiling', issues);
  const physicalSize = readPhysicalSize(input.physicalSize, 'physicalSize', issues);
  const textureRef = readString(input.textureRef, 'textureRef', issues);
  const color = readColor(input.color, 'color', issues);

  switch (kind) {
    case 'paint': {
      if (!color) {
        issues.push('paint overlay requires color');
      }
      if (issues.length > 0) {
        throw new OverlayValidationError(issues);
      }
      const overlay: Overlay = {
        id,
        kind: 'paint',
        color: color as string,
        opacity,
        blendMode,
        transform,
        maskByNormal,
      };
      if (textureRef) {
        overlay.textureRef = textureRef;
      }
      if (tiling) {
        overlay.tiling = tiling;
      }
      if (physicalSize) {
        overlay.physicalSize = physicalSize;
      }
      if (targetSurface) {
        overlay.targetSurface = targetSurface;
      }
      return overlay;
    }
    case 'wallpaper': {
      if (!textureRef) {
        issues.push('wallpaper overlay requires textureRef');
      }
      if (!tiling && !physicalSize) {
        issues.push('wallpaper overlay requires tiling or physicalSize (pattern size)');
      }
      if (issues.length > 0) {
        throw new OverlayValidationError(issues);
      }
      const overlay: Overlay = {
        id,
        kind: 'wallpaper',
        textureRef: textureRef as string,
        opacity,
        blendMode,
        transform,
        maskByNormal,
      };
      if (color) {
        overlay.color = color;
      }
      if (tiling) {
        overlay.tiling = tiling;
      }
      if (physicalSize) {
        overlay.physicalSize = physicalSize;
      }
      if (targetSurface) {
        overlay.targetSurface = targetSurface;
      }
      return overlay;
    }
    case 'sticker': {
      if (!textureRef) {
        issues.push('sticker overlay requires textureRef');
      }
      if (!physicalSize) {
        issues.push('sticker overlay requires physicalSize (exact real-world dimensions)');
      }
      if (issues.length > 0) {
        throw new OverlayValidationError(issues);
      }
      const overlay: Overlay = {
        id,
        kind: 'sticker',
        textureRef: textureRef as string,
        physicalSize: physicalSize as PhysicalSize,
        opacity,
        blendMode,
        transform,
        maskByNormal,
      };
      if (color) {
        overlay.color = color;
      }
      if (tiling) {
        overlay.tiling = tiling;
      }
      if (targetSurface) {
        overlay.targetSurface = targetSurface;
      }
      return overlay;
    }
    default:
      return assertNever(kind);
  }
}

/**
 * Cria um overlay canônico a partir de um draft (gera `id` se ausente).
 */
export function createOverlay(draft: OverlayDraft): Overlay {
  const id = draft.id ?? newOverlayId();
  const transform = mergeTransform(defaultTransform(), draft.transform);
  const maskByNormal: MaskByNormal = {
    ...defaultMaskByNormal(),
    ...draft.maskByNormal,
  };
  return validateOverlay({
    ...draft,
    id,
    opacity: draft.opacity ?? 1,
    blendMode: draft.blendMode ?? 'normal',
    transform,
    maskByNormal,
  });
}

/** Mescla um patch e revalida (kind pode mudar se os campos obrigatórios vierem no patch). */
export function mergeOverlay(current: Overlay, patch: OverlayPatch): Overlay {
  const transform = mergeTransform(current.transform, patch.transform);
  const maskByNormal: MaskByNormal = {
    ...current.maskByNormal,
    ...patch.maskByNormal,
  };
  const tiling = patch.tiling !== undefined ? patch.tiling : current.tiling;
  const physicalSize = patch.physicalSize !== undefined ? patch.physicalSize : current.physicalSize;
  const targetSurface =
    patch.targetSurface !== undefined ? patch.targetSurface : current.targetSurface;

  return validateOverlay({
    ...current,
    ...patch,
    transform,
    maskByNormal,
    tiling,
    physicalSize,
    targetSurface,
  });
}
