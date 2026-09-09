import { getAccessToken, isDevAuthBypass } from './supabase';

/**
 * Contrato de API assumido (codificado neste cliente — 2026-09-04).
 *
 * Auth
 *   Authorization: Bearer <supabase access_token>
 *   Dev: VITE_DEV_AUTH_BYPASS=1 envia `Bearer dev-bypass`.
 *
 * POST /jobs
 *   multipart/form-data:
 *     - `file` — um vídeo  OU  `files[]` — N imagens
 *     - `user_height_m` — string decimal em metros (ex.: "1.75")
 *     - `idempotency_key` — uuid por tentativa
 *   header extra: `Idempotency-Key: <uuid>`
 *   200/201: { job_id, state }
 *
 * GET /jobs
 *   200: [{ job_id, state, created_at, source_kind, progress }]
 *
 * GET /jobs/{id}
 *   200: { job_id, state, stages: { extracting: {status, progress}, ... },
 *          error_code, error_message }
 *
 * DELETE /jobs/{id} → 204
 *
 * WS  /jobs/{id}/events
 *   Auth no canal: query `token` (compat: `access_token`) e header Bearer.
 *
 * Erros FastAPI: { detail: { message, code } }. Legado { error_code, message } ainda é lido.
 */

const DEFAULT_API_URL = 'http://localhost:8000';
const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);
const MAX_RETRIES = 3;
const RETRY_BASE_MS = 400;

export interface ResolveApiBaseUrlInput {
  envUrl?: string | null;
  origin?: string;
  port?: string;
}

function isLoopbackHostname(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
}

/** URL bakeada de dev (`localhost:8000`) — ignorada quando a UI não está no Vite. */
export function isLoopbackApiUrl(url: string): boolean {
  try {
    return isLoopbackHostname(new URL(url).hostname);
  } catch {
    return false;
  }
}

/**
 * Resolve a base da API.
 * No Vite (:5173) usa `VITE_API_URL` ou localhost:8000.
 * Fora disso, um localhost bakeado (ou vazio) cai na origem da página —
 * o build servido em :2222 não pode chamar a porta 8000 da máquina do usuário.
 */
export function resolveApiBaseUrl(input: ResolveApiBaseUrlInput): string {
  const fromEnv = typeof input.envUrl === 'string' ? input.envUrl.trim().replace(/\/+$/, '') : '';
  const origin = input.origin?.replace(/\/+$/, '') ?? '';
  const viteDev = input.port === '5173';
  if (viteDev) {
    return fromEnv || DEFAULT_API_URL;
  }
  if (origin) {
    if (!fromEnv || isLoopbackApiUrl(fromEnv)) {
      return origin;
    }
    return fromEnv;
  }
  return fromEnv || DEFAULT_API_URL;
}

export function apiConnectionErrorMessage(baseUrl: string): string {
  let portHint = '';
  try {
    const port = new URL(baseUrl).port;
    if (port) {
      portHint = ` (porta ${port})`;
    }
  } catch {
    portHint = '';
  }
  return `Não foi possível conectar à API em ${baseUrl}. Verifique se o backend está em execução${portHint}.`;
}

export type JobState =
  | 'queued'
  | 'extracting'
  | 'sfm'
  | 'training'
  | 'exporting'
  | 'meshproxy'
  | 'autocal'
  | 'done'
  | 'error'
  | 'cancelled';

export type SourceKind = 'video' | 'images' | 'gif' | 'ply';

export type StageStatus = 'pending' | 'running' | 'done' | 'failed' | 'skipped';

export type PipelineStage =
  'extracting' | 'sfm' | 'training' | 'exporting' | 'meshproxy' | 'autocal';

export interface StageProgress {
  status: StageStatus;
  progress: number;
  message?: string | null;
}

export interface JobSummary {
  job_id: string;
  state: JobState;
  created_at: string;
  source_kind: SourceKind;
  progress: number;
}

export interface JobDetail {
  job_id: string;
  state: JobState;
  stages: Partial<Record<PipelineStage, StageProgress>>;
  error_code: string | null;
  error_message: string | null;
  source_kind?: SourceKind;
  created_at?: string;
  scene_id?: string | null;
  eta_seconds?: number | null;
}

export interface CreateJobResponse {
  job_id: string;
  state: JobState;
}

export interface ApiErrorDetail {
  message?: string;
  code?: string;
  error_code?: string;
}

export interface ApiErrorBody {
  error_code?: string;
  message?: string;
  detail?: string | ApiErrorDetail;
}

export interface JobListEnvelope {
  jobs: JobSummary[];
}

export class ApiError extends Error {
  readonly status?: number;
  readonly errorCode?: string;

  constructor(message: string, status?: number, errorCode?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorCode = errorCode;
  }
}

export function getApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_URL;
  const envUrl = typeof raw === 'string' ? raw : '';
  if (typeof window !== 'undefined' && window.location?.origin) {
    return resolveApiBaseUrl({
      envUrl,
      origin: window.location.origin,
      port: window.location.port,
    });
  }
  return resolveApiBaseUrl({ envUrl });
}

export function isRetryableStatus(status: number): boolean {
  return RETRYABLE_STATUS.has(status);
}

export async function getAuthHeaders(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  if (isDevAuthBypass()) {
    return { Authorization: 'Bearer dev-bypass' };
  }
  return {};
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function messageFromBody(
  body: ApiErrorBody | null,
  status: number,
): { message: string; code?: string } {
  if (!body) {
    return { message: `Erro ${status} ao comunicar com a API.` };
  }
  if (body.detail && typeof body.detail === 'object') {
    const nested = body.detail.message?.trim();
    const code = body.detail.code ?? body.detail.error_code ?? body.error_code;
    if (nested) {
      return { message: nested, code };
    }
    if (code) {
      return { message: `Erro ${status} (${code}).`, code };
    }
  }
  if (typeof body.detail === 'string' && body.detail.trim().length > 0) {
    return { message: body.detail, code: body.error_code };
  }
  if (body.message && body.message.trim().length > 0) {
    return { message: body.message, code: body.error_code };
  }
  return { message: `Erro ${status} ao comunicar com a API.`, code: body.error_code };
}

export function parseApiErrorBody(text: string, status: number): ApiError {
  if (!text) {
    return new ApiError(`Erro ${status} ao comunicar com a API.`, status);
  }
  try {
    const body = JSON.parse(text) as ApiErrorBody;
    const parsed = messageFromBody(body, status);
    return new ApiError(parsed.message, status, parsed.code);
  } catch {
    return new ApiError(text, status);
  }
}

async function parseJson<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  if (!response.ok) {
    throw parseApiErrorBody(text, response.status);
  }
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
  options: { retry?: boolean } = {},
): Promise<T> {
  const retry = options.retry ?? (init.method === undefined || init.method === 'GET');
  const headers = new Headers(init.headers);
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }
  const auth = await getAuthHeaders();
  for (const [key, value] of Object.entries(auth)) {
    if (!headers.has(key)) {
      headers.set(key, value);
    }
  }

  let lastError: unknown;
  const attempts = retry ? MAX_RETRIES : 1;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(`${getApiBaseUrl()}${path}`, {
        ...init,
        headers,
      });
      if (!response.ok && retry && isRetryableStatus(response.status) && attempt < attempts - 1) {
        await sleep(RETRY_BASE_MS * 2 ** attempt);
        continue;
      }
      return await parseJson<T>(response);
    } catch (error) {
      lastError = error;
      const networkFailure = !(error instanceof ApiError);
      const retryableApi =
        error instanceof ApiError && error.status !== undefined && isRetryableStatus(error.status);
      if (retry && attempt < attempts - 1 && (networkFailure || retryableApi)) {
        await sleep(RETRY_BASE_MS * 2 ** attempt);
        continue;
      }
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(apiConnectionErrorMessage(getApiBaseUrl()));
    }
  }
  if (lastError instanceof ApiError) {
    throw lastError;
  }
  throw new ApiError(apiConnectionErrorMessage(getApiBaseUrl()));
}

export interface CreateJobInput {
  files: File[];
  sourceKind: SourceKind;
  userHeightM: string;
  idempotencyKey: string;
  onUploadProgress?: (percent: number) => void;
  signal?: AbortSignal;
}

function appendJobFields(form: FormData, input: CreateJobInput): void {
  switch (input.sourceKind) {
    case 'video':
    case 'gif':
    case 'ply': {
      const single = input.files[0];
      if (single) {
        form.append('file', single);
      }
      break;
    }
    case 'images': {
      for (const image of input.files) {
        form.append('files[]', image);
      }
      break;
    }
    default: {
      const exhaustive: never = input.sourceKind;
      throw new ApiError(`Tipo de origem não suportado: ${String(exhaustive)}`);
    }
  }
  form.append('user_height_m', input.userHeightM);
  form.append('idempotency_key', input.idempotencyKey);
}

export function createJob(input: CreateJobInput): Promise<CreateJobResponse> {
  const form = new FormData();
  appendJobFields(form, input);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${getApiBaseUrl()}/jobs`);
    xhr.responseType = 'text';

    const onAbort = () => {
      xhr.abort();
    };
    if (input.signal) {
      if (input.signal.aborted) {
        reject(new ApiError('Upload cancelado.', 499));
        return;
      }
      input.signal.addEventListener('abort', onAbort, { once: true });
    }

    void getAuthHeaders().then((auth) => {
      for (const [key, value] of Object.entries(auth)) {
        xhr.setRequestHeader(key, value);
      }
      xhr.setRequestHeader('Accept', 'application/json');
      xhr.setRequestHeader('Idempotency-Key', input.idempotencyKey);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && event.total > 0) {
          input.onUploadProgress?.(Math.round((event.loaded / event.total) * 100));
        }
      };

      xhr.onload = () => {
        input.signal?.removeEventListener('abort', onAbort);
        const status = xhr.status;
        const text = xhr.responseText ?? '';
        if (status < 200 || status >= 300) {
          reject(parseApiErrorBody(text, status));
          return;
        }
        try {
          resolve(JSON.parse(text) as CreateJobResponse);
        } catch {
          reject(new ApiError('A API devolveu uma resposta inválida ao criar o job.', status));
        }
      };

      xhr.onerror = () => {
        input.signal?.removeEventListener('abort', onAbort);
        reject(new ApiError('Não foi possível enviar os arquivos. Verifique a conexão com a API.'));
      };

      xhr.onabort = () => {
        input.signal?.removeEventListener('abort', onAbort);
        reject(new ApiError('Upload cancelado.', 499));
      };

      xhr.send(form);
    });
  });
}

const PIPELINE_STAGE_NAMES: readonly PipelineStage[] = [
  'extracting',
  'sfm',
  'training',
  'exporting',
  'meshproxy',
  'autocal',
];

function isPipelineStageName(value: string): value is PipelineStage {
  return (PIPELINE_STAGE_NAMES as readonly string[]).includes(value);
}

function normalizeSummary(
  raw: JobSummary & { overall_progress?: number; progress?: number },
): JobSummary {
  return {
    ...raw,
    progress: raw.progress ?? raw.overall_progress ?? 0,
  };
}

function normalizeStages(raw: unknown): Partial<Record<PipelineStage, StageProgress>> {
  if (!raw) {
    return {};
  }
  if (Array.isArray(raw)) {
    const out: Partial<Record<PipelineStage, StageProgress>> = {};
    for (const item of raw) {
      if (!item || typeof item !== 'object') {
        continue;
      }
      const record = item as {
        name?: string;
        status?: StageStatus;
        progress?: number;
        message?: string;
      };
      if (typeof record.name === 'string' && isPipelineStageName(record.name)) {
        out[record.name] = {
          status: record.status ?? 'pending',
          progress: record.progress ?? 0,
          message: record.message,
        };
      }
    }
    return out;
  }
  if (typeof raw === 'object') {
    return raw as Partial<Record<PipelineStage, StageProgress>>;
  }
  return {};
}

export async function listJobs(): Promise<JobSummary[]> {
  const payload = await request<JobListEnvelope | JobSummary[]>('/jobs');
  const list = Array.isArray(payload) ? payload : (payload.jobs ?? []);
  return list.map(normalizeSummary);
}

export async function getJob(jobId: string): Promise<JobDetail> {
  const raw = await request<JobDetail & { stages?: unknown; overall_progress?: number }>(
    `/jobs/${encodeURIComponent(jobId)}`,
  );
  return {
    ...raw,
    error_code: raw.error_code ?? null,
    error_message: raw.error_message ?? null,
    stages: normalizeStages(raw.stages),
  };
}

export async function deleteJob(jobId: string): Promise<void> {
  await request<void>(`/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' }, { retry: false });
}

export const jobsApi = {
  create: createJob,
  list: listJobs,
  get: getJob,
  delete: deleteJob,
};
