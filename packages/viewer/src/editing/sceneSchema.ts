import type { Overlay as OverlayJson } from '@gs/overlays/types';

import type { TRS } from '../math/trs';
import type { SplatFormat, SplatQuality } from '../renderer/SplatRenderer';

export type { Overlay as OverlayJson, OverlayKind } from '@gs/overlays/types';

/** Versão atual do JSON de cena. Incremente ao quebrar compatibilidade. */
export const SCENE_SCHEMA_VERSION = 1 as const;

export type SceneSchemaVersion = typeof SCENE_SCHEMA_VERSION;

export type SceneNodeKind = 'glb' | 'splat';

/** Autocal emits auto-height|manual; `none` is the viewer initial state. */
export type CalibrationSource = 'auto-height' | 'manual' | 'none';

export interface BackgroundSplatJson {
  id: string;
  name: string;
  uri: string;
  format: SplatFormat;
  visible: boolean;
  trs?: TRS;
  quality?: Partial<SplatQuality>;
}

export interface SceneNodeJson {
  id: string;
  name: string;
  kind: SceneNodeKind;
  uri: string;
  format: 'glb' | 'gltf' | 'ply' | 'ksplat';
  visible: boolean;
  locked: boolean;
  trs: TRS;
  parentId: string | null;
}

/**
 * Scene calibration fragment. Matches autocal `to_scene_dict()` camelCase
 * plus optional live-tape `reference` and initial `source: "none"`.
 */
export type TemporalSourceKind = 'none' | 'gif' | 'video' | 'sequence';

export interface TemporalJson {
  enabled: boolean;
  frameCount: number;
  durationS: number | null;
  fps: number | null;
  currentTime: number;
  sourceKind: TemporalSourceKind;
  times?: number[];
  cameras?: TemporalCameraJson[];
  clusters?: Record<string, unknown>[];
}

export type RelightMode = 'baked-sh' | 'preview' | 'sh-env' | 'unsupported';

export interface RelightJson {
  enabled: boolean;
  mode: RelightMode;
  hasSphericalHarmonics: boolean;
  shDegree: number | null;
  azimuthDeg?: number;
  elevationDeg?: number;
  intensity?: number;
}

export interface TemporalCameraJson {
  t: number;
  position: [number, number, number];
  target: [number, number, number];
  name?: string;
  /** Eixo up já em Y-up (Three). Sem ele o lookAt usa (0,1,0) e rola a captura. */
  up?: [number, number, number];
  /** FOV vertical em graus (COLMAP fy + altura). */
  fovY?: number;
}

export const DEFAULT_TEMPORAL: TemporalJson = Object.freeze({
  enabled: false,
  frameCount: 0,
  durationS: null,
  fps: null,
  currentTime: 0,
  sourceKind: 'none',
});

export const DEFAULT_RELIGHT: RelightJson = Object.freeze({
  enabled: false,
  mode: 'sh-env',
  hasSphericalHarmonics: true,
  shDegree: 3,
  azimuthDeg: 45,
  elevationDeg: 35,
  intensity: 1,
});

export interface CalibrationJson {
  scaleFactor: number | null;
  source: CalibrationSource;
  confidence: number | null;
  framesUsed?: number;
  estimatedPersonHeightSceneUnits?: number | null;
  errorEstimate?: number | null;
  warnings?: string[];
  reference?: {
    sceneDistance: number;
    realLengthMm: string;
  };
}

export interface SceneDocument {
  schemaVersion: SceneSchemaVersion;
  id: string;
  name: string;
  backgroundSplat: BackgroundSplatJson | null;
  nodes: SceneNodeJson[];
  calibration: CalibrationJson;
  overlays: OverlayJson[];
  temporal: TemporalJson;
  relight: RelightJson;
}

export const DEFAULT_CALIBRATION: CalibrationJson = Object.freeze({
  scaleFactor: null,
  source: 'none',
  confidence: null,
  framesUsed: 0,
  estimatedPersonHeightSceneUnits: null,
  errorEstimate: null,
  warnings: [],
});

export function createEmptySceneDocument(name = 'Cena sem título'): SceneDocument {
  return {
    schemaVersion: SCENE_SCHEMA_VERSION,
    id: '',
    name,
    backgroundSplat: null,
    nodes: [],
    calibration: { ...DEFAULT_CALIBRATION },
    overlays: [],
    temporal: { ...DEFAULT_TEMPORAL },
    relight: { ...DEFAULT_RELIGHT },
  };
}
