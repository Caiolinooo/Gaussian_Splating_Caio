import { assertNever } from './assertNever';
import {
  isLengthUnit,
  type Overlay,
  type PhysicalLength,
  type PhysicalSize,
  type Tiling,
} from './types';
import type { UnitsPort } from './units-port';

/** Repeat/offset UV efetivo enviado aos uniforms. */
export interface TextureRepeatOffset {
  repeatU: number;
  repeatV: number;
  offsetU: number;
  offsetV: number;
}

/** Extensão do frustum do projetor em unidades de cena. */
export interface SceneExtents {
  width: number;
  height: number;
}

export interface ComputePhysicalRepeatInput {
  /** Largura do frustum do projetor em unidades de cena. */
  projectorWidthScene: number;
  /** Altura do frustum do projetor em unidades de cena. */
  projectorHeightScene: number;
  /** Largura física de um tile da estampa (ex.: 10 cm). */
  patternWidth: PhysicalLength;
  /** Altura física de um tile da estampa. */
  patternHeight: PhysicalLength;
  /**
   * Metros reais por unidade de cena (`worldMeters = scene * factor`).
   * Deve ser o mesmo fator do nó-raiz calibrado.
   */
  sceneMetersPerUnit: number;
  offsetU?: number;
  offsetV?: number;
}

/**
 * Converte um comprimento físico para metros.
 * Usa `UnitsPort.convert` quando fornecido; senão a tabela mm local.
 */
export function lengthToMeters(length: PhysicalLength, units?: Pick<UnitsPort, 'convert'>): number {
  if (!isLengthUnit(length.unit)) {
    throw new Error(`Unsupported length unit: ${String(length.unit)}`);
  }
  if (!Number.isFinite(length.value) || length.value <= 0) {
    throw new Error(`Physical length must be a finite value > 0, got ${String(length.value)}`);
  }
  if (units) {
    return units.convert(length.value, length.unit, 'm');
  }
  const mm: Record<typeof length.unit, number> = {
    mm: 1,
    cm: 10,
    m: 1000,
    in: 25.4,
    ft: 304.8,
  };
  return (length.value * mm[length.unit]) / 1000;
}

/** `metros = sceneUnits * sceneMetersPerUnit`. */
export function sceneExtentToMeters(sceneUnits: number, sceneMetersPerUnit: number): number {
  if (!Number.isFinite(sceneUnits) || sceneUnits <= 0) {
    throw new Error(`Scene extent must be finite and > 0, got ${String(sceneUnits)}`);
  }
  if (!Number.isFinite(sceneMetersPerUnit) || sceneMetersPerUnit <= 0) {
    throw new Error(`sceneMetersPerUnit must be finite and > 0, got ${String(sceneMetersPerUnit)}`);
  }
  return sceneUnits * sceneMetersPerUnit;
}

/**
 * Dimensão física → unidades de cena.
 * `scene = meters / sceneMetersPerUnit`.
 */
export function physicalSizeToSceneExtents(
  size: PhysicalSize,
  sceneMetersPerUnit: number,
  units?: Pick<UnitsPort, 'convert'>,
): SceneExtents {
  if (!Number.isFinite(sceneMetersPerUnit) || sceneMetersPerUnit <= 0) {
    throw new Error(`sceneMetersPerUnit must be finite and > 0, got ${String(sceneMetersPerUnit)}`);
  }
  const widthM = lengthToMeters(size.width, units);
  const heightM = lengthToMeters(size.height, units);
  return {
    width: widthM / sceneMetersPerUnit,
    height: heightM / sceneMetersPerUnit,
  };
}

/**
 * Repeat UV a partir da escala real do padrão.
 *
 * ```
 * projectorMeters = projectorScene * sceneMetersPerUnit
 * repeat          = projectorMeters / patternMeters
 * ```
 *
 * Ex.: projetor de 2 m, estampa de 10 cm, fator 1 m/unidade → repeat = 20.
 */
export function computePhysicalRepeat(input: ComputePhysicalRepeatInput): TextureRepeatOffset {
  const widthM = sceneExtentToMeters(input.projectorWidthScene, input.sceneMetersPerUnit);
  const heightM = sceneExtentToMeters(input.projectorHeightScene, input.sceneMetersPerUnit);
  const patternWM = lengthToMeters(input.patternWidth);
  const patternHM = lengthToMeters(input.patternHeight);
  return {
    repeatU: widthM / patternWM,
    repeatV: heightM / patternHM,
    offsetU: input.offsetU ?? 0,
    offsetV: input.offsetV ?? 0,
  };
}

function tilingOrDefault(tiling: Tiling | undefined): TextureRepeatOffset {
  return {
    repeatU: tiling?.repeatU ?? 1,
    repeatV: tiling?.repeatV ?? 1,
    offsetU: tiling?.offsetU ?? 0,
    offsetV: tiling?.offsetV ?? 0,
  };
}

/**
 * Resolve o tiling efetivo de um overlay (tiling explícito vence o físico).
 */
export function resolveTiling(overlay: Overlay, units: UnitsPort): TextureRepeatOffset {
  switch (overlay.kind) {
    case 'paint':
      return tilingOrDefault(overlay.tiling);
    case 'sticker':
      return {
        repeatU: 1,
        repeatV: 1,
        offsetU: overlay.tiling?.offsetU ?? 0,
        offsetV: overlay.tiling?.offsetV ?? 0,
      };
    case 'wallpaper': {
      if (overlay.tiling) {
        return tilingOrDefault(overlay.tiling);
      }
      if (overlay.physicalSize) {
        return computePhysicalRepeat({
          projectorWidthScene: overlay.transform.scale.x,
          projectorHeightScene: overlay.transform.scale.y,
          patternWidth: overlay.physicalSize.width,
          patternHeight: overlay.physicalSize.height,
          sceneMetersPerUnit: units.sceneMetersPerUnit(),
          offsetU: 0,
          offsetV: 0,
        });
      }
      throw new Error('Wallpaper overlay requires tiling or physicalSize');
    }
    default:
      return assertNever(overlay);
  }
}

/**
 * Tamanho do frustum do projetor em unidades de cena.
 * Sticker (e paint com `physicalSize`) derivam do tamanho real; o resto usa `transform.scale`.
 */
export function resolveProjectorSizeScene(
  overlay: Overlay,
  units: UnitsPort,
): SceneExtents & {
  depth: number;
} {
  const depth = overlay.transform.scale.z;
  switch (overlay.kind) {
    case 'sticker': {
      const extents = physicalSizeToSceneExtents(
        overlay.physicalSize,
        units.sceneMetersPerUnit(),
        units,
      );
      return { ...extents, depth };
    }
    case 'paint': {
      if (overlay.physicalSize) {
        const extents = physicalSizeToSceneExtents(
          overlay.physicalSize,
          units.sceneMetersPerUnit(),
          units,
        );
        return { ...extents, depth };
      }
      return {
        width: overlay.transform.scale.x,
        height: overlay.transform.scale.y,
        depth,
      };
    }
    case 'wallpaper':
      return {
        width: overlay.transform.scale.x,
        height: overlay.transform.scale.y,
        depth,
      };
    default:
      return assertNever(overlay);
  }
}
