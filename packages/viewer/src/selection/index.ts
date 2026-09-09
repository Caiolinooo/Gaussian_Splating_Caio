/**
 * Módulo de seleção de splats (puro, sem `three`).
 *
 * Pipeline típica (SparkBackend):
 *   1. `projectCenter` — centro → pixels (viewProjection + viewport).
 *   2. `pointInRect` / `pointInPolygon` — teste 2D; `pointInSphere` / `pointInBox` — teste 3D.
 *   3. `composeSelection` — união/subtração/interseção segundo `SelectMode`.
 *   4. `SelectionManager` — estado da seleção ativa + AABB.
 */

export {
  forEachProjectedCenter,
  projectCenter,
  type ProjectedPoint,
  type ViewportSize,
} from './projectSplats';

export {
  pointInBox,
  pointInPolygon,
  pointInRect,
  pointInSphere,
  type BoxShape,
  type RectLike,
  type ScreenPoint,
  type SphereShape,
} from './pointInShape';

export { composeSelection, type SelectMode } from './composeSelection';

export { SelectionManager, type Bounds3 } from './SelectionManager';
