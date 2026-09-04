import {
  parseOverlayDocument,
  type Overlay,
  type OverlayDocument,
  type OverlayKind,
} from '@gs/overlays';
import type { OverlayJson, OverlayKind as SceneOverlayKind } from '@gs/viewer';

import { assertNever } from '../viewer/assertNever';

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function overlayKindLabelPt(kind: OverlayKind): string {
  switch (kind) {
    case 'paint':
      return 'Pintura';
    case 'wallpaper':
      return 'Papel de parede';
    case 'sticker':
      return 'Adesivo';
    default:
      return assertNever(kind);
  }
}

export function toSceneOverlayKind(kind: OverlayKind): SceneOverlayKind {
  return kind;
}

export function overlayTextureOrColor(overlay: Overlay): string {
  switch (overlay.kind) {
    case 'paint':
      return overlay.textureRef ?? overlay.color;
    case 'wallpaper':
    case 'sticker':
      return overlay.textureRef;
    default:
      return assertNever(overlay);
  }
}

/** SceneDocument.overlays is the canonical `@gs/overlays` model. */
export function toSceneOverlaySummaries(overlays: readonly Overlay[]): OverlayJson[] {
  return overlays.slice();
}

/** Lê `overlayDocument` do payload da API, se presente e válido. */
export function extractOverlayDocument(raw: unknown): OverlayDocument | null {
  if (!isRecord(raw)) {
    return null;
  }
  const candidate = raw.overlayDocument;
  if (candidate == null) {
    return null;
  }
  if (isRecord(candidate) && candidate.schemaVersion === 1 && Array.isArray(candidate.overlays)) {
    try {
      return parseOverlayDocument(candidate);
    } catch {
      return null;
    }
  }
  return null;
}
