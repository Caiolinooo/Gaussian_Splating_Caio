/**
 * Cliente HTTP do viewer 3D (artefatos de job + JSON de cena versionado).
 *
 * ## Base URL
 * `import.meta.env.VITE_API_URL` — se ausente, usa `http://localhost:8000`.
 *
 * ## Endpoints (contrato assumido até a API real estabilizar)
 *
 * ### `GET /jobs/{jobId}/artifacts/ksplat`
 * Entrega o splat web. Aceita:
 * - corpo **binário** (`application/octet-stream` ou `application/x-ksplat`);
 * - JSON `{ "url": string }` / `{ "href": string }` com URL pré-assinada;
 * - header `Location` com o mesmo significado.
 *
 * ### `GET /jobs/{jobId}/artifacts/ply`
 * Idem para o `.ply` mestre (fallback se não houver ksplat).
 *
 * ### `GET /scenes/{sceneId}`
 * Devolve um `SceneApiDocument` (schemaVersion 1) **ou** um envelope
 * `{ scene | document: SceneApiDocument }`. Campos extras de calibração
 * (`framesUsed`, `errorEstimate`, `warnings`) e `overlayDocument` são
 * preservados pelo cliente e ignorados pelo `SceneManager.fromDocument`.
 *
 * ### `PUT /scenes/{sceneId}`
 * Corpo: `SceneApiDocument`. Resposta: o documento persistido (mesmo formato)
 * ou `{ scene | document }`.
 *
 * Autenticação: Bearer da sessão Supabase (`lib/supabase.ts`).
 */

import type { OverlayDocument } from '@gs/overlays';
import type { CalibrationJson, SceneDocument } from '@gs/viewer';

import { getAccessToken, isDevAuthBypass } from './supabase';

const DEFAULT_API_URL = 'http://localhost:8000';

export function getViewerApiBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_API_URL;
  if (typeof fromEnv === 'string' && fromEnv.length > 0) {
    return fromEnv.replace(/\/$/, '');
  }
  return DEFAULT_API_URL;
}

/** Metadados de auto-calibração que o schema do SceneManager ainda não tipa. */
export interface CalibrationExtras {
  framesUsed?: number;
  errorEstimate?: number | null;
  warnings?: string[];
}

export type SceneApiCalibration = CalibrationJson & CalibrationExtras;

/**
 * Documento persistido na API: SceneDocument + extras de calibração +
 * documento canônico de overlays (`@gs/overlays`).
 */
export interface SceneApiDocument extends SceneDocument {
  calibration: SceneApiCalibration;
  overlayDocument?: OverlayDocument;
}

export type SplatArtifactKind = 'ksplat' | 'ply';

export interface ArtifactPayload {
  kind: SplatArtifactKind;
  buffer: ArrayBuffer;
  sourceUrl?: string;
}

export class ViewerApiError extends Error {
  readonly status?: number;
  readonly path: string;

  constructor(message: string, path: string, status?: number) {
    super(message);
    this.name = 'ViewerApiError';
    this.path = path;
    this.status = status;
  }
}

export const MISSING_SPLAT_USER_MESSAGE =
  'Não encontramos o splat deste job. Ele pode não existir, ainda estar processando ou ter falhado no pipeline.';

export function isMissingSplatArtifact(error: unknown): boolean {
  return error instanceof ViewerApiError && error.status === 404;
}

export interface FetchArtifactOptions {
  onProgress?: (ratio: number) => void;
  signal?: AbortSignal;
}

async function authHeaders(): Promise<HeadersInit> {
  const headers: Record<string, string> = {};
  const token = await getAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
    return headers;
  }
  if (isDevAuthBypass()) {
    headers.Authorization = 'Bearer dev-bypass';
  }
  return headers;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as {
      detail?: string | { message?: string; code?: string };
      message?: string;
    };
    if (body.detail && typeof body.detail === 'object' && body.detail.message) {
      return body.detail.message;
    }
    if (typeof body.detail === 'string' && body.detail.length > 0) {
      return body.detail;
    }
    if (typeof body.message === 'string' && body.message.length > 0) {
      return body.message;
    }
  } catch {
    // corpo não-JSON
  }
  return fallback;
}

function unwrapScenePayload(raw: unknown): unknown {
  if (!isRecord(raw)) {
    return raw;
  }
  if (raw.schemaVersion === 1) {
    return raw;
  }
  if (isRecord(raw.scene)) {
    return raw.scene;
  }
  if (isRecord(raw.document)) {
    return raw.document;
  }
  return raw;
}

function asSceneApiDocument(raw: unknown): SceneApiDocument {
  const unwrapped = unwrapScenePayload(raw);
  if (!isRecord(unwrapped) || unwrapped.schemaVersion !== 1) {
    throw new ViewerApiError('Resposta da API não é um SceneDocument schemaVersion 1.', '/scenes');
  }
  return unwrapped as unknown as SceneApiDocument;
}

async function readBinaryWithProgress(
  response: Response,
  onProgress?: (ratio: number) => void,
): Promise<ArrayBuffer> {
  const totalHeader = response.headers.get('content-length');
  const total = totalHeader ? Number(totalHeader) : 0;
  if (!response.body || !onProgress) {
    return response.arrayBuffer();
  }
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let loaded = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    if (value) {
      chunks.push(value);
      loaded += value.byteLength;
      if (total > 0) {
        onProgress(Math.min(1, loaded / total));
      }
    }
  }
  const out = new Uint8Array(loaded);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.byteLength;
  }
  onProgress(1);
  return out.buffer;
}

function looksJson(contentType: string | null): boolean {
  return contentType !== null && contentType.includes('application/json');
}

/**
 * Baixa o artefato `.ksplat` ou `.ply` de um job.
 * Preferir ksplat no viewer web; ply é o fallback de fidelidade.
 */
export async function fetchJobArtifact(
  jobId: string,
  kind: SplatArtifactKind,
  options: FetchArtifactOptions = {},
): Promise<ArtifactPayload> {
  const path = `/jobs/${encodeURIComponent(jobId)}/artifacts/${kind}`;
  const url = `${getViewerApiBaseUrl()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      headers: { Accept: 'application/octet-stream, application/json', ...(await authHeaders()) },
      signal: options.signal,
    });
  } catch {
    throw new ViewerApiError(
      'Não foi possível conectar à API para baixar o splat. Verifique o backend.',
      path,
    );
  }

  if (response.status === 404) {
    throw new ViewerApiError(MISSING_SPLAT_USER_MESSAGE, path, 404);
  }
  if (!response.ok) {
    const detail = await readErrorDetail(
      response,
      `Erro ${response.status} ao baixar o artefato ${kind}.`,
    );
    throw new ViewerApiError(detail, path, response.status);
  }

  const location = response.headers.get('Location');
  if (
    location &&
    looksJson(response.headers.get('content-type')) === false &&
    response.status >= 300
  ) {
    return fetchJobArtifactFromUrl(location, kind, options);
  }

  if (looksJson(response.headers.get('content-type'))) {
    const body = (await response.json()) as unknown;
    if (isRecord(body)) {
      const remote =
        typeof body.url === 'string' ? body.url : typeof body.href === 'string' ? body.href : null;
      if (remote) {
        return fetchJobArtifactFromUrl(remote, kind, options);
      }
    }
    throw new ViewerApiError('JSON de artefato sem campo url/href.', path, response.status);
  }

  const buffer = await readBinaryWithProgress(response, options.onProgress);
  return { kind, buffer, sourceUrl: url };
}

async function fetchJobArtifactFromUrl(
  remoteUrl: string,
  kind: SplatArtifactKind,
  options: FetchArtifactOptions,
): Promise<ArtifactPayload> {
  let response: Response;
  try {
    response = await fetch(remoteUrl, { signal: options.signal });
  } catch {
    throw new ViewerApiError('Falha ao baixar o splat da URL pré-assinada.', remoteUrl);
  }
  if (!response.ok) {
    throw new ViewerApiError(
      `Erro ${response.status} na URL do artefato.`,
      remoteUrl,
      response.status,
    );
  }
  const buffer = await readBinaryWithProgress(response, options.onProgress);
  return { kind, buffer, sourceUrl: remoteUrl };
}

/** Lê a cena versionada. 404 → `null` (o viewer cria um documento vazio). */
export async function fetchScene(
  sceneId: string,
  signal?: AbortSignal,
): Promise<SceneApiDocument | null> {
  const path = `/scenes/${encodeURIComponent(sceneId)}`;
  const url = `${getViewerApiBaseUrl()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      headers: { Accept: 'application/json', ...(await authHeaders()) },
      signal,
    });
  } catch {
    throw new ViewerApiError('Não foi possível conectar à API para abrir a cena.', path);
  }
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    const detail = await readErrorDetail(response, `Erro ${response.status} ao abrir a cena.`);
    throw new ViewerApiError(detail, path, response.status);
  }
  return asSceneApiDocument(await response.json());
}

/** Persiste a cena (nós, calibração, overlays canônicos). */
export async function putScene(
  sceneId: string,
  document: SceneApiDocument,
): Promise<SceneApiDocument> {
  const path = `/scenes/${encodeURIComponent(sceneId)}`;
  const url = `${getViewerApiBaseUrl()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: 'PUT',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...(await authHeaders()),
      },
      body: JSON.stringify(document),
    });
  } catch {
    throw new ViewerApiError('Não foi possível conectar à API para salvar a cena.', path);
  }
  if (!response.ok) {
    const detail = await readErrorDetail(response, `Erro ${response.status} ao salvar a cena.`);
    throw new ViewerApiError(detail, path, response.status);
  }
  const raw: unknown = await response.json().catch(() => document);
  try {
    return asSceneApiDocument(raw);
  } catch {
    return document;
  }
}

/** Extrai extras de calibração sem alterar o schema do SceneManager. */
export function extractCalibrationExtras(calibration: unknown): CalibrationExtras {
  if (!isRecord(calibration)) {
    return {};
  }
  const extras: CalibrationExtras = {};
  if (typeof calibration.framesUsed === 'number' && Number.isFinite(calibration.framesUsed)) {
    extras.framesUsed = calibration.framesUsed;
  }
  if (typeof calibration.errorEstimate === 'number' && Number.isFinite(calibration.errorEstimate)) {
    extras.errorEstimate = calibration.errorEstimate;
  }
  if (Array.isArray(calibration.warnings)) {
    extras.warnings = calibration.warnings.filter(
      (item): item is string => typeof item === 'string',
    );
  }
  return extras;
}

export function mergeCalibrationForApi(
  calibration: CalibrationJson,
  extras: CalibrationExtras,
): SceneApiCalibration {
  return {
    ...calibration,
    ...extras,
  };
}
