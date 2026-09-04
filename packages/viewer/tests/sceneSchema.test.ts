import { defaultMaskByNormal, defaultTransform } from '@gs/overlays/types';
import { describe, expect, it } from 'vitest';

import { createEmptySceneDocument, SCENE_SCHEMA_VERSION } from '../src/editing/sceneSchema';
import {
  cloneSceneDocument,
  parseSceneDocument,
  SceneSchemaError,
  serializeSceneDocument,
} from '../src/editing/serialize';
import { createTRS } from '../src/math/trs';

const sample = {
  schemaVersion: SCENE_SCHEMA_VERSION,
  id: 'scene-roundtrip',
  name: 'Sala de estar',
  backgroundSplat: {
    id: 'bg-1',
    name: 'Scan',
    uri: 'https://cdn.example/scan.ksplat',
    format: 'ksplat' as const,
    visible: true,
    trs: createTRS({ position: { x: 1, y: 2, z: 3 } }),
    quality: { shDegree: 2 as const, alphaRemovalThreshold: 5 },
  },
  nodes: [
    {
      id: 'chair',
      name: 'Cadeira',
      kind: 'glb' as const,
      uri: 'assets/chair.glb',
      format: 'glb' as const,
      visible: true,
      locked: false,
      trs: createTRS({
        position: { x: 0.5, y: 0, z: -1 },
        scale: { x: 1, y: 1, z: 1 },
      }),
      parentId: null,
    },
    {
      id: 'extra-splat',
      name: 'Vaso',
      kind: 'splat' as const,
      uri: 'assets/vase.ply',
      format: 'ply' as const,
      visible: false,
      locked: true,
      trs: createTRS(),
      parentId: 'chair',
    },
  ],
  calibration: {
    scaleFactor: 1.75,
    source: 'auto-height' as const,
    confidence: 0.82,
    framesUsed: 24,
    estimatedPersonHeightSceneUnits: 2.394,
    errorEstimate: 0.041,
    warnings: [],
    reference: { sceneDistance: 1.12, realLengthMm: '1750' },
  },
  overlays: [
    {
      id: 'ov-1',
      kind: 'wallpaper' as const,
      textureRef: 'assets/wall.png',
      opacity: 0.9,
      blendMode: 'normal' as const,
      transform: defaultTransform(),
      maskByNormal: defaultMaskByNormal(),
      physicalSize: {
        width: { value: 10, unit: 'cm' as const },
        height: { value: 10, unit: 'cm' as const },
      },
    },
  ],
};

describe('JSON de cena', () => {
  it('faz round-trip serialize → parse', () => {
    const json = serializeSceneDocument(sample);
    const parsed = parseSceneDocument(json);
    expect(parsed).toEqual(sample);
  });

  it('clone é estruturalmente igual e independente', () => {
    const cloned = cloneSceneDocument(sample);
    expect(cloned).toEqual(sample);
    cloned.name = 'Outro';
    expect(sample.name).toBe('Sala de estar');
  });

  it('aceita documento vazio com placeholders', () => {
    const empty = createEmptySceneDocument('Nova');
    empty.id = 'x';
    const parsed = parseSceneDocument(serializeSceneDocument(empty));
    expect(parsed.backgroundSplat).toBeNull();
    expect(parsed.nodes).toEqual([]);
    expect(parsed.overlays).toEqual([]);
    expect(parsed.calibration.source).toBe('none');
    expect(parsed.schemaVersion).toBe(1);
  });

  it('rejeita schemaVersion desconhecido', () => {
    expect(() => parseSceneDocument({ schemaVersion: 99, nodes: [] })).toThrow(SceneSchemaError);
  });

  it('rejeita JSON inválido', () => {
    expect(() => parseSceneDocument('{nope')).toThrow(SceneSchemaError);
  });

  it('preenche format padrão conforme kind', () => {
    const parsed = parseSceneDocument({
      schemaVersion: 1,
      id: 's',
      name: 'n',
      backgroundSplat: null,
      nodes: [{ id: 'a', name: 'Mesh', kind: 'glb', uri: 'a.glb', trs: {} }],
      calibration: {},
      overlays: [],
    });
    expect(parsed.nodes[0]?.format).toBe('glb');
  });
});
