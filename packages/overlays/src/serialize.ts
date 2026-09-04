import { OVERLAY_SCHEMA_VERSION, type Overlay, type OverlayDocument } from './types';
import { OverlayValidationError, validateOverlay } from './validate';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Empacota a lista de overlays no documento versionado do JSON de cena.
 */
export function toOverlayDocument(overlays: readonly Overlay[]): OverlayDocument {
  const ids = new Set<string>();
  const canonical: Overlay[] = [];
  for (const overlay of overlays) {
    const valid = validateOverlay(overlay);
    if (ids.has(valid.id)) {
      throw new OverlayValidationError(`Duplicate overlay id: ${valid.id}`);
    }
    ids.add(valid.id);
    canonical.push(valid);
  }
  return {
    schemaVersion: OVERLAY_SCHEMA_VERSION,
    overlays: canonical,
  };
}

/**
 * Serializa o documento para JSON (round-trip com `parseOverlayDocument`).
 */
export function stringifyOverlayDocument(doc: OverlayDocument): string {
  const canonical = toOverlayDocument(doc.overlays);
  if (doc.schemaVersion !== OVERLAY_SCHEMA_VERSION) {
    throw new OverlayValidationError(
      `Unsupported overlay schemaVersion: ${String(doc.schemaVersion)}`,
    );
  }
  return JSON.stringify(canonical);
}

/**
 * Lê um documento de overlays a partir de objeto ou string JSON.
 * Rejeita `schemaVersion` diferente da versão suportada.
 */
export function parseOverlayDocument(input: unknown): OverlayDocument {
  const raw: unknown = typeof input === 'string' ? parseJson(input) : input;
  if (!isRecord(raw)) {
    throw new OverlayValidationError('Overlay document must be an object');
  }
  if (raw.schemaVersion !== OVERLAY_SCHEMA_VERSION) {
    throw new OverlayValidationError(
      `Unsupported overlay schemaVersion: ${String(raw.schemaVersion)} (expected ${OVERLAY_SCHEMA_VERSION})`,
    );
  }
  if (!Array.isArray(raw.overlays)) {
    throw new OverlayValidationError('overlays must be an array');
  }
  return toOverlayDocument(raw.overlays);
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new OverlayValidationError('Overlay document is not valid JSON');
  }
}

/** Clone JSON-safe (sem undefined) para persistência. */
export function cloneOverlay(overlay: Overlay): Overlay {
  return validateOverlay(JSON.parse(JSON.stringify(overlay)) as unknown);
}
