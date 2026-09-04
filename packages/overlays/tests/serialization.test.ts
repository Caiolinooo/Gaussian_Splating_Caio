import { describe, expect, it } from 'vitest';

import { OverlayCollection } from '../src/overlayCollection';
import {
  parseOverlayDocument,
  stringifyOverlayDocument,
  toOverlayDocument,
} from '../src/serialize';
import { OVERLAY_SCHEMA_VERSION } from '../src/types';
import { OverlayValidationError, createOverlay } from '../src/validate';

function sampleOverlays() {
  return [
    createOverlay({
      id: 'paint-wall',
      kind: 'paint',
      color: '#c4b5a0',
      opacity: 0.85,
      blendMode: 'multiply',
      targetSurface: 'wall-north',
    }),
    createOverlay({
      id: 'paper-1',
      kind: 'wallpaper',
      textureRef: 'assets/damask.png',
      physicalSize: {
        width: { value: 10, unit: 'cm' },
        height: { value: 10, unit: 'cm' },
      },
      transform: { scale: { x: 3.2, y: 2.4, z: 0.3 } },
    }),
    createOverlay({
      id: 'sticker-logo',
      kind: 'sticker',
      textureRef: 'assets/logo.png',
      physicalSize: {
        width: { value: 30, unit: 'cm' },
        height: { value: 45, unit: 'cm' },
      },
      maskByNormal: { enabled: true, threshold: 0.6 },
    }),
  ];
}

describe('serialização round-trip', () => {
  it('documento → JSON → parse preserva os três kinds e a ordem', () => {
    const overlays = sampleOverlays();
    const doc = toOverlayDocument(overlays);
    expect(doc.schemaVersion).toBe(OVERLAY_SCHEMA_VERSION);

    const json = stringifyOverlayDocument(doc);
    const parsed = parseOverlayDocument(json);

    expect(parsed.schemaVersion).toBe(1);
    expect(parsed.overlays.map((item) => item.id)).toEqual([
      'paint-wall',
      'paper-1',
      'sticker-logo',
    ]);
    expect(parsed).toEqual(doc);
    expect(parsed.overlays[2]).toMatchObject({
      kind: 'sticker',
      physicalSize: {
        width: { value: 30, unit: 'cm' },
        height: { value: 45, unit: 'cm' },
      },
    });
  });

  it('OverlayCollection.serialize / replaceFromDocument é invertível', () => {
    const collection = new OverlayCollection();
    for (const overlay of sampleOverlays()) {
      collection.add({
        ...overlay,
        id: overlay.id,
      });
    }
    const snapshot = collection.serialize();
    const restored = new OverlayCollection();
    restored.replaceFromDocument(JSON.parse(JSON.stringify(snapshot)));
    expect(restored.serialize()).toEqual(snapshot);
    expect(restored.list().map((item) => item.kind)).toEqual(['paint', 'wallpaper', 'sticker']);
  });

  it('setOrder altera a ordem persistida', () => {
    const collection = new OverlayCollection();
    collection.add({ id: 'a', kind: 'paint', color: '#111111' });
    collection.add({ id: 'b', kind: 'paint', color: '#222222' });
    collection.add({ id: 'c', kind: 'paint', color: '#333333' });
    collection.setOrder(['c', 'a', 'b']);
    expect(collection.serialize().overlays.map((item) => item.id)).toEqual(['c', 'a', 'b']);
  });

  it('rejeita schemaVersion desconhecida', () => {
    expect(() =>
      parseOverlayDocument({
        schemaVersion: 99,
        overlays: [],
      }),
    ).toThrow(OverlayValidationError);
    expect(() =>
      parseOverlayDocument({
        schemaVersion: 99,
        overlays: [],
      }),
    ).toThrow(/schemaVersion/);
  });

  it('rejeita ids duplicados no documento', () => {
    const paint = createOverlay({ id: 'dup', kind: 'paint', color: '#000000' });
    expect(() => toOverlayDocument([paint, paint])).toThrow(/Duplicate overlay id/);
  });

  it('rejeita JSON malformado', () => {
    expect(() => parseOverlayDocument('{not-json')).toThrow(/not valid JSON/);
  });
});
