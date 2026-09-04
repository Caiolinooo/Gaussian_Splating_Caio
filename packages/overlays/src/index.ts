export { assertNever } from './assertNever';
export { OverlayCollection, type OverlayCollectionListener } from './overlayCollection';
export {
  OverlayManager,
  collectTargetMeshes,
  type OverlayManagerOptions,
  type OverlayTextureLoader,
} from './OverlayManager';
export {
  passesNormalMask,
  shouldKeepFragment,
  surfaceFacing,
  thresholdFromMaxAngleRadians,
  type NormalMaskParams,
  type Vec3,
} from './normalMask';
export {
  computePhysicalRepeat,
  lengthToMeters,
  physicalSizeToSceneExtents,
  resolveProjectorSizeScene,
  resolveTiling,
  sceneExtentToMeters,
  type ComputePhysicalRepeatInput,
  type SceneExtents,
  type TextureRepeatOffset,
} from './physicalTiling';
export {
  OVERLAY_RENDER_ORDER_BASE,
  ProjectiveDecal,
  syncProjectorCamera,
  type ProjectiveDecalOptions,
} from './projection/ProjectiveDecal';
export {
  cloneOverlay,
  parseOverlayDocument,
  stringifyOverlayDocument,
  toOverlayDocument,
} from './serialize';
export {
  blendingGlsl,
  overlayFragmentBody,
  overlayFragmentShader,
  overlayVertexShader,
} from './shaders/sources';
export {
  DEFAULT_NORMAL_THRESHOLD,
  LENGTH_UNITS,
  OVERLAY_SCHEMA_VERSION,
  blendModeToIndex,
  defaultMaskByNormal,
  defaultTransform,
  isBlendMode,
  isLengthUnit,
  isOverlayKind,
  isPaintOverlay,
  isStickerOverlay,
  isWallpaperOverlay,
  overlayKindLabel,
  overlayKindToIndex,
  type BlendMode,
  type LengthUnit,
  type MaskByNormal,
  type Overlay,
  type OverlayDocument,
  type OverlayDraft,
  type OverlayKind,
  type OverlayPatch,
  type OverlaySchemaVersion,
  type OverlayTransform,
  type PaintOverlay,
  type PhysicalLength,
  type PhysicalSize,
  type StickerOverlay,
  type Tiling,
  type Vec3Tuple,
  type WallpaperOverlay,
} from './types';
export { createFallbackUnitsPort, type UnitsPort } from './units-port';
export { createUnitsBinding } from './unitsBinding';
export { OverlayValidationError, createOverlay, mergeOverlay, validateOverlay } from './validate';
