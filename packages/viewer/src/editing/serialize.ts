import { OverlayValidationError, validateOverlay } from '@gs/overlays/validate';

import { createId } from '../ids';
import { cloneTRS, createTRS, type TRS } from '../math/trs';
import { assertNever } from '../assertNever';
import {
  DEFAULT_CALIBRATION,
  DEFAULT_RELIGHT,
  DEFAULT_TEMPORAL,
  SCENE_SCHEMA_VERSION,
  type BackgroundSplatJson,
  type CalibrationJson,
  type CalibrationSource,
  type OverlayJson,
  type RelightJson,
  type RelightMode,
  type SceneDocument,
  type SceneNodeJson,
  type SceneNodeKind,
  type TemporalJson,
  type TemporalSourceKind,
} from './sceneSchema';

export class SceneSchemaError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'SceneSchemaError';
    this.code = code;
  }
}

/** Serializa o documento de cena para JSON estável (pretty-print). */
export function serializeSceneDocument(doc: SceneDocument): string {
  return JSON.stringify(normalizeDocument(doc), null, 2);
}

/** Faz parse + validação. Lança `SceneSchemaError` se o schema for inválido. */
export function parseSceneDocument(input: unknown): SceneDocument {
  const raw = typeof input === 'string' ? parseJson(input) : input;
  if (!isRecord(raw)) {
    throw new SceneSchemaError('not-object', 'JSON de cena deve ser um objeto.');
  }
  const version = raw.schemaVersion;
  if (version !== SCENE_SCHEMA_VERSION) {
    throw new SceneSchemaError(
      'unsupported-version',
      `schemaVersion não suportado: ${String(version)} (esperado ${SCENE_SCHEMA_VERSION}).`,
    );
  }
  return normalizeDocument({
    schemaVersion: SCENE_SCHEMA_VERSION,
    id: readString(raw.id, 'id') || createId('scene'),
    name: readString(raw.name, 'name') || 'Cena sem título',
    backgroundSplat: parseBackground(raw.backgroundSplat),
    nodes: parseNodes(raw.nodes),
    calibration: parseCalibration(raw.calibration),
    overlays: parseOverlays(raw.overlays),
    temporal: parseTemporal(raw.temporal),
    relight: parseRelight(raw.relight),
  });
}

export function cloneSceneDocument(doc: SceneDocument): SceneDocument {
  return parseSceneDocument(JSON.parse(serializeSceneDocument(doc)) as unknown);
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new SceneSchemaError('invalid-json', 'JSON de cena inválido.');
  }
}

function normalizeDocument(doc: SceneDocument): SceneDocument {
  return {
    schemaVersion: SCENE_SCHEMA_VERSION,
    id: doc.id,
    name: doc.name,
    backgroundSplat: doc.backgroundSplat ? cloneBackground(doc.backgroundSplat) : null,
    nodes: doc.nodes.map(cloneNode),
    calibration: cloneCalibration(doc.calibration),
    overlays: doc.overlays.map(cloneOverlay),
    temporal: cloneTemporal(doc.temporal ?? DEFAULT_TEMPORAL),
    relight: cloneRelight(doc.relight ?? DEFAULT_RELIGHT),
  };
}

function cloneBackground(bg: BackgroundSplatJson): BackgroundSplatJson {
  return {
    id: bg.id,
    name: bg.name,
    uri: bg.uri,
    format: bg.format,
    visible: bg.visible,
    trs: bg.trs ? cloneTRS(bg.trs) : undefined,
    quality: bg.quality ? { ...bg.quality } : undefined,
  };
}

function cloneNode(node: SceneNodeJson): SceneNodeJson {
  return {
    id: node.id,
    name: node.name,
    kind: node.kind,
    uri: node.uri,
    format: node.format,
    visible: node.visible,
    locked: node.locked,
    trs: cloneTRS(node.trs),
    parentId: node.parentId,
  };
}

function cloneCalibration(cal: CalibrationJson): CalibrationJson {
  return {
    scaleFactor: cal.scaleFactor,
    source: cal.source,
    confidence: cal.confidence,
    framesUsed: cal.framesUsed,
    estimatedPersonHeightSceneUnits: cal.estimatedPersonHeightSceneUnits,
    errorEstimate: cal.errorEstimate,
    warnings: cal.warnings ? [...cal.warnings] : undefined,
    reference: cal.reference
      ? {
          sceneDistance: cal.reference.sceneDistance,
          realLengthMm: cal.reference.realLengthMm,
        }
      : undefined,
  };
}

function cloneOverlay(overlay: OverlayJson): OverlayJson {
  return { ...overlay };
}

function cloneTemporal(temporal: TemporalJson): TemporalJson {
  return {
    enabled: temporal.enabled,
    frameCount: temporal.frameCount,
    durationS: temporal.durationS,
    fps: temporal.fps,
    currentTime: temporal.currentTime,
    sourceKind: temporal.sourceKind,
    times: temporal.times ? [...temporal.times] : undefined,
    cameras: temporal.cameras ? temporal.cameras.map((camera) => ({ ...camera })) : undefined,
    clusters: temporal.clusters ? temporal.clusters.map((cluster) => ({ ...cluster })) : undefined,
  };
}

function cloneRelight(relight: RelightJson): RelightJson {
  return {
    enabled: relight.enabled,
    mode: relight.mode,
    hasSphericalHarmonics: relight.hasSphericalHarmonics,
    shDegree: relight.shDegree,
    azimuthDeg: relight.azimuthDeg,
    elevationDeg: relight.elevationDeg,
    intensity: relight.intensity,
  };
}

function parseBackground(value: unknown): BackgroundSplatJson | null {
  if (value == null) {
    return null;
  }
  if (!isRecord(value)) {
    throw new SceneSchemaError('background', 'backgroundSplat deve ser objeto ou null.');
  }
  const format = value.format;
  if (format !== 'ply' && format !== 'ksplat') {
    throw new SceneSchemaError('background-format', 'backgroundSplat.format deve ser ply|ksplat.');
  }
  return {
    id: readString(value.id, 'backgroundSplat.id') || createId('bg'),
    name: readString(value.name, 'backgroundSplat.name') || 'Splat de fundo',
    uri: readString(value.uri, 'backgroundSplat.uri'),
    format,
    visible: value.visible !== false,
    trs: value.trs ? parseTRS(value.trs) : undefined,
    quality: parseQuality(value.quality),
  };
}

function parseNodes(value: unknown): SceneNodeJson[] {
  if (value == null) {
    return [];
  }
  if (!Array.isArray(value)) {
    throw new SceneSchemaError('nodes', 'nodes deve ser um array.');
  }
  return value.map((item, index) => parseNode(item, index));
}

function parseNode(value: unknown, index: number): SceneNodeJson {
  if (!isRecord(value)) {
    throw new SceneSchemaError('node', `nodes[${index}] deve ser objeto.`);
  }
  const kind = parseNodeKind(value.kind, index);
  return {
    id: readString(value.id, `nodes[${index}].id`) || createId('node'),
    name: readString(value.name, `nodes[${index}].name`) || `Objeto ${index + 1}`,
    kind,
    uri: readString(value.uri, `nodes[${index}].uri`),
    format: parseNodeFormat(value.format, kind, index),
    visible: value.visible !== false,
    locked: value.locked === true,
    trs: parseTRS(value.trs),
    parentId:
      value.parentId == null ? null : readString(value.parentId, `nodes[${index}].parentId`),
  };
}

function parseNodeKind(value: unknown, index: number): SceneNodeKind {
  switch (value) {
    case 'glb':
    case 'splat':
      return value;
    default:
      throw new SceneSchemaError('node-kind', `nodes[${index}].kind inválido: ${String(value)}`);
  }
}

function parseNodeFormat(
  value: unknown,
  kind: SceneNodeKind,
  index: number,
): SceneNodeJson['format'] {
  if (value == null) {
    switch (kind) {
      case 'glb':
        return 'glb';
      case 'splat':
        return 'ksplat';
      default:
        return assertNever(kind);
    }
  }
  if (value === 'glb' || value === 'gltf' || value === 'ply' || value === 'ksplat') {
    return value;
  }
  throw new SceneSchemaError('node-format', `nodes[${index}].format inválido: ${String(value)}`);
}

function parseQuality(value: unknown): BackgroundSplatJson['quality'] {
  if (value == null) {
    return undefined;
  }
  if (!isRecord(value)) {
    throw new SceneSchemaError('quality', 'quality deve ser objeto.');
  }
  const quality: BackgroundSplatJson['quality'] = {};
  if (value.shDegree != null) {
    const degree = readNumber(value.shDegree, 'quality.shDegree');
    if (degree === 0 || degree === 1 || degree === 2 || degree === 3) {
      quality.shDegree = degree;
    } else {
      throw new SceneSchemaError('quality-sh', `quality.shDegree inválido: ${degree}`);
    }
  }
  if (value.alphaRemovalThreshold != null) {
    quality.alphaRemovalThreshold = readNumber(
      value.alphaRemovalThreshold,
      'quality.alphaRemovalThreshold',
    );
  }
  return quality;
}

function parseCalibration(value: unknown): CalibrationJson {
  if (value == null) {
    return { ...DEFAULT_CALIBRATION };
  }
  if (!isRecord(value)) {
    throw new SceneSchemaError('calibration', 'calibration deve ser objeto.');
  }
  return {
    scaleFactor:
      value.scaleFactor == null ? null : readNumber(value.scaleFactor, 'calibration.scaleFactor'),
    source: parseCalibrationSource(value.source),
    confidence:
      value.confidence == null ? null : readNumber(value.confidence, 'calibration.confidence'),
    framesUsed:
      value.framesUsed == null ? undefined : readInt(value.framesUsed, 'calibration.framesUsed'),
    estimatedPersonHeightSceneUnits:
      value.estimatedPersonHeightSceneUnits == null
        ? undefined
        : readNumber(
            value.estimatedPersonHeightSceneUnits,
            'calibration.estimatedPersonHeightSceneUnits',
          ),
    errorEstimate:
      value.errorEstimate == null
        ? undefined
        : readNumber(value.errorEstimate, 'calibration.errorEstimate'),
    warnings: parseWarnings(value.warnings),
    reference: value.reference == null ? undefined : parseReference(value.reference),
  };
}

function parseTemporal(value: unknown): TemporalJson {
  if (value == null) {
    return { ...DEFAULT_TEMPORAL };
  }
  if (!isRecord(value)) {
    throw new SceneSchemaError('temporal', 'temporal deve ser objeto.');
  }
  const sourceKind = parseTemporalSourceKind(value.sourceKind);
  const frameCount =
    value.frameCount == null ? 0 : readInt(value.frameCount, 'temporal.frameCount');
  return {
    enabled: value.enabled === true || (sourceKind !== 'none' && frameCount > 1),
    frameCount,
    durationS: value.durationS == null ? null : readNumber(value.durationS, 'temporal.durationS'),
    fps: value.fps == null ? null : readNumber(value.fps, 'temporal.fps'),
    currentTime:
      value.currentTime == null ? 0 : readNumber(value.currentTime, 'temporal.currentTime'),
    sourceKind,
    times: Array.isArray(value.times)
      ? value.times.filter((item): item is number => typeof item === 'number')
      : undefined,
    cameras: Array.isArray(value.cameras) ? (value.cameras as TemporalJson['cameras']) : undefined,
    clusters: Array.isArray(value.clusters)
      ? (value.clusters as TemporalJson['clusters'])
      : undefined,
  };
}

function parseTemporalSourceKind(value: unknown): TemporalSourceKind {
  switch (value) {
    case 'none':
    case 'gif':
    case 'video':
    case 'sequence':
      return value;
    case undefined:
    case null:
      return 'none';
    default:
      throw new SceneSchemaError(
        'temporal-source',
        `temporal.sourceKind inválido: ${String(value)}`,
      );
  }
}

function parseRelight(value: unknown): RelightJson {
  if (value == null) {
    return { ...DEFAULT_RELIGHT };
  }
  if (!isRecord(value)) {
    throw new SceneSchemaError('relight', 'relight deve ser objeto.');
  }
  return {
    enabled: value.enabled !== false,
    mode: parseRelightMode(value.mode),
    hasSphericalHarmonics: value.hasSphericalHarmonics !== false,
    shDegree: value.shDegree == null ? 3 : readInt(value.shDegree, 'relight.shDegree'),
    azimuthDeg: value.azimuthDeg == null ? 45 : readNumber(value.azimuthDeg, 'relight.azimuthDeg'),
    elevationDeg:
      value.elevationDeg == null ? 35 : readNumber(value.elevationDeg, 'relight.elevationDeg'),
    intensity: value.intensity == null ? 1 : readNumber(value.intensity, 'relight.intensity'),
  };
}

function parseRelightMode(value: unknown): RelightMode {
  switch (value) {
    case 'baked-sh':
    case 'preview':
    case 'sh-env':
    case 'unsupported':
      return value;
    case undefined:
    case null:
      return 'sh-env';
    default:
      throw new SceneSchemaError('relight-mode', `relight.mode inválido: ${String(value)}`);
  }
}

function parseCalibrationSource(value: unknown): CalibrationSource {
  switch (value) {
    case 'auto-height':
    case 'manual':
    case 'none':
      return value;
    case undefined:
    case null:
      return 'none';
    default:
      throw new SceneSchemaError(
        'calibration-source',
        `calibration.source inválido: ${String(value)}`,
      );
  }
}

function parseReference(value: unknown): NonNullable<CalibrationJson['reference']> {
  if (!isRecord(value)) {
    throw new SceneSchemaError('calibration-reference', 'calibration.reference deve ser objeto.');
  }
  return {
    sceneDistance: readNumber(value.sceneDistance, 'calibration.reference.sceneDistance'),
    realLengthMm: String(value.realLengthMm ?? ''),
  };
}

function parseOverlays(value: unknown): OverlayJson[] {
  if (value == null) {
    return [];
  }
  if (!Array.isArray(value)) {
    throw new SceneSchemaError('overlays', 'overlays deve ser um array.');
  }
  return value.map((item, index) => parseOverlay(item, index));
}

function parseOverlay(value: unknown, index: number): OverlayJson {
  try {
    return validateOverlay(value);
  } catch (error) {
    if (error instanceof OverlayValidationError) {
      throw new SceneSchemaError('overlay', `overlays[${index}]: ${error.message}`);
    }
    throw error;
  }
}

function parseWarnings(value: unknown): string[] | undefined {
  if (value == null) {
    return undefined;
  }
  if (!Array.isArray(value)) {
    throw new SceneSchemaError('calibration-warnings', 'calibration.warnings deve ser um array.');
  }
  return value.map((item, index) => {
    if (typeof item !== 'string') {
      throw new SceneSchemaError(
        'calibration-warnings',
        `calibration.warnings[${index}] deve ser string.`,
      );
    }
    return item;
  });
}

function readInt(value: unknown, label: string): number {
  const n = readNumber(value, label);
  if (!Number.isInteger(n)) {
    throw new SceneSchemaError('integer', `${label} deve ser inteiro.`);
  }
  return n;
}

function parseTRS(value: unknown): TRS {
  if (value == null) {
    return createTRS();
  }
  if (!isRecord(value)) {
    throw new SceneSchemaError('trs', 'trs deve ser objeto.');
  }
  return createTRS({
    position: parseVec(value.position, 'position'),
    rotation: parseQuat(value.rotation),
    scale: parseVec(value.scale, 'scale', 1),
  });
}

function parseVec(
  value: unknown,
  label: string,
  fallback = 0,
): { x: number; y: number; z: number } {
  if (value == null) {
    return { x: fallback, y: fallback, z: fallback };
  }
  if (!isRecord(value)) {
    throw new SceneSchemaError('vec3', `${label} deve ser {x,y,z}.`);
  }
  return {
    x: readNumber(value.x ?? fallback, `${label}.x`),
    y: readNumber(value.y ?? fallback, `${label}.y`),
    z: readNumber(value.z ?? fallback, `${label}.z`),
  };
}

function parseQuat(value: unknown): { x: number; y: number; z: number; w: number } {
  if (value == null) {
    return { x: 0, y: 0, z: 0, w: 1 };
  }
  if (!isRecord(value)) {
    throw new SceneSchemaError('quat', 'rotation deve ser {x,y,z,w}.');
  }
  return {
    x: readNumber(value.x ?? 0, 'rotation.x'),
    y: readNumber(value.y ?? 0, 'rotation.y'),
    z: readNumber(value.z ?? 0, 'rotation.z'),
    w: readNumber(value.w ?? 1, 'rotation.w'),
  };
}

function readString(value: unknown, label: string): string {
  if (value == null) {
    return '';
  }
  if (typeof value !== 'string') {
    throw new SceneSchemaError('string', `${label} deve ser string.`);
  }
  return value;
}

function readNumber(value: unknown, label: string): number {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    throw new SceneSchemaError('number', `${label} deve ser number.`);
  }
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === 'object' && !Array.isArray(value);
}
