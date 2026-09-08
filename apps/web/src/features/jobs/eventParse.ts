import type { JobState, PipelineStage } from '../../lib/api';

export interface JobEventMetrics {
  eta_seconds?: number;
  error_code?: string;
  registered_images?: number;
  num_gaussians?: number;
  psnr?: number;
  scale_factor?: number;
  confidence?: number;
  [key: string]: unknown;
}

export type ReconnectDecision = 'stop' | 'retry' | 'fallback';

export function shouldAttemptReconnect(input: {
  closed: boolean;
  terminalReached: boolean;
  attempt: number;
  maxAttempts: number;
}): ReconnectDecision {
  if (input.closed || input.terminalReached) {
    return 'stop';
  }
  if (input.attempt + 1 >= input.maxAttempts) {
    return 'fallback';
  }
  return 'retry';
}

export interface JobEvent {
  state: JobState;
  stage: PipelineStage | 'upload' | null;
  stage_progress: number;
  overall_progress: number;
  message: string;
  metrics: JobEventMetrics;
}

const JOB_STATES: readonly JobState[] = [
  'queued',
  'extracting',
  'sfm',
  'training',
  'exporting',
  'meshproxy',
  'autocal',
  'done',
  'error',
  'cancelled',
];

const STAGES: readonly (PipelineStage | 'upload')[] = [
  'upload',
  'extracting',
  'sfm',
  'training',
  'exporting',
  'meshproxy',
  'autocal',
];

export function isJobState(value: unknown): value is JobState {
  return typeof value === 'string' && (JOB_STATES as readonly string[]).includes(value);
}

export function isPipelineStage(value: unknown): value is PipelineStage | 'upload' {
  return typeof value === 'string' && (STAGES as readonly string[]).includes(value);
}

/** Normaliza 0–1 ou 0–100 para fração 0–1. */
export function normalizeProgress(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 0;
  }
  const fraction = value > 1 ? value / 100 : value;
  return Math.min(1, Math.max(0, fraction));
}

function asMetrics(value: unknown): JobEventMetrics {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as JobEventMetrics;
  }
  return {};
}

/** Parser puro — aceita objeto JSON ou envelope SSE `data: {...}`. */
export function parseJobEvent(raw: unknown): JobEvent | null {
  let payload: unknown = raw;
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (trimmed.length === 0 || trimmed === '[DONE]') {
      return null;
    }
    const dataLine = trimmed.startsWith('data:') ? trimmed.slice(5).trim() : trimmed;
    try {
      payload = JSON.parse(dataLine);
    } catch {
      return null;
    }
  }
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const nested =
    record.data && typeof record.data === 'object'
      ? (record.data as Record<string, unknown>)
      : record;
  if (!isJobState(nested.state)) {
    return null;
  }
  const stageValue = nested.stage;
  const stage =
    stageValue === null || stageValue === undefined
      ? null
      : isPipelineStage(stageValue)
        ? stageValue
        : null;
  return {
    state: nested.state,
    stage,
    stage_progress: normalizeProgress(nested.stage_progress),
    overall_progress: normalizeProgress(nested.overall_progress),
    message: typeof nested.message === 'string' ? nested.message : '',
    metrics: asMetrics(nested.metrics),
  };
}

export function httpToWsUrl(httpUrl: string): string {
  const url = new URL(httpUrl);
  if (url.protocol === 'https:') {
    url.protocol = 'wss:';
  } else {
    url.protocol = 'ws:';
  }
  return url.toString();
}
