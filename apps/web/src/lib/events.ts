import {
  httpToWsUrl,
  parseJobEvent,
  shouldAttemptReconnect,
  type JobEvent,
} from '../features/jobs/eventParse';
import { isTerminalState } from '../features/jobs/stages';
import { getApiBaseUrl, getAuthHeaders } from './api';
import { getAccessToken } from './supabase';

export {
  httpToWsUrl,
  isJobState,
  isPipelineStage,
  normalizeProgress,
  parseJobEvent,
  shouldAttemptReconnect,
  type JobEvent,
  type JobEventMetrics,
  type ReconnectDecision,
} from '../features/jobs/eventParse';

/**
 * Cliente WS/SSE para ` /jobs/{id}/events `.
 *
 * Ordem: WebSocket → reconexão exponencial → SSE (fetch + Authorization) →
 * callback de polling. Eventos tipados: { state, stage, stage_progress,
 * overall_progress, message, metrics }.
 */

export type EventTransport = 'ws' | 'sse' | 'poll';

export type EventsConnectionState = 'connecting' | 'live' | 'reconnecting' | 'polling' | 'closed';

export interface SubscribeJobEventsOptions {
  onEvent: (event: JobEvent) => void;
  onState?: (state: EventsConnectionState, transport: EventTransport) => void;
  onFallbackPoll?: () => void;
  shouldStopReconnect?: () => boolean;
  wsMaxAttempts?: number;
  sseMaxAttempts?: number;
  pollIntervalMs?: number;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
}

function eventsPath(jobId: string): string {
  return `/jobs/${encodeURIComponent(jobId)}/events`;
}

async function eventsUrl(jobId: string, withTokenQuery: boolean): Promise<string> {
  const url = new URL(`${getApiBaseUrl()}${eventsPath(jobId)}`);
  if (withTokenQuery) {
    const token = await getAccessToken();
    if (token) {
      url.searchParams.set('token', token);
    }
  }
  return url.toString();
}

function backoffMs(attempt: number, initial: number, max: number): number {
  const raw = initial * 2 ** Math.max(0, attempt);
  const jitter = raw * (0.2 * Math.random());
  return Math.min(max, Math.round(raw + jitter));
}

function parseSseChunk(buffer: string, onEvent: (event: JobEvent) => void): string {
  const parts = buffer.split(/\r?\n\r?\n/);
  const rest = parts.pop() ?? '';
  for (const block of parts) {
    const dataLines: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim());
      }
    }
    if (dataLines.length === 0) {
      continue;
    }
    const parsed = parseJobEvent(dataLines.join('\n'));
    if (parsed) {
      onEvent(parsed);
    }
  }
  return rest;
}

export function subscribeJobEvents(jobId: string, options: SubscribeJobEventsOptions): () => void {
  const wsMaxAttempts = options.wsMaxAttempts ?? 5;
  const sseMaxAttempts = options.sseMaxAttempts ?? 4;
  const pollIntervalMs = options.pollIntervalMs ?? 2000;
  const initialBackoffMs = options.initialBackoffMs ?? 500;
  const maxBackoffMs = options.maxBackoffMs ?? 15_000;

  let closed = false;
  let terminalReached = false;
  let socket: WebSocket | null = null;
  let abortSse: AbortController | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let transport: EventTransport = 'ws';

  const setState = (state: EventsConnectionState) => {
    if (terminalReached && (state === 'reconnecting' || state === 'connecting')) {
      options.onState?.('closed', transport);
      return;
    }
    options.onState?.(state, transport);
  };

  const finishTerminal = () => {
    terminalReached = true;
    closed = true;
    clearTimers();
    if (socket) {
      socket.close();
      socket = null;
    }
    abortSse?.abort();
    abortSse = null;
    setState('closed');
  };

  const deliverEvent = (event: JobEvent) => {
    options.onEvent(event);
    if (isTerminalState(event.state)) {
      finishTerminal();
    }
  };

  const stopReconnect = (): boolean =>
    closed || terminalReached || Boolean(options.shouldStopReconnect?.());

  const clearTimers = () => {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };

  const startPolling = () => {
    if (closed || pollTimer !== null) {
      return;
    }
    transport = 'poll';
    setState('polling');
    options.onFallbackPoll?.();
    pollTimer = setInterval(() => {
      if (!closed) {
        options.onFallbackPoll?.();
      }
    }, pollIntervalMs);
  };

  const connectSse = (attempt: number) => {
    if (stopReconnect()) {
      return;
    }
    transport = 'sse';
    setState(attempt === 0 ? 'connecting' : 'reconnecting');
    abortSse = new AbortController();

    void (async () => {
      try {
        const headers = await getAuthHeaders();
        const response = await fetch(await eventsUrl(jobId, false), {
          headers: { ...headers, Accept: 'text/event-stream' },
          signal: abortSse.signal,
        });
        if (!response.ok || !response.body) {
          if (response.status === 404 || response.status === 405) {
            startPolling();
            return;
          }
          throw new Error(`sse-http-${response.status}`);
        }
        setState('live');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (!closed) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }
          buffer = parseSseChunk(buffer + decoder.decode(value, { stream: true }), deliverEvent);
        }
        if (stopReconnect()) {
          return;
        }
        throw new Error('sse-ended');
      } catch (error) {
        if (closed || (error instanceof DOMException && error.name === 'AbortError')) {
          return;
        }
        const decision = shouldAttemptReconnect({
          closed,
          terminalReached,
          attempt,
          maxAttempts: sseMaxAttempts,
        });
        if (decision === 'stop') {
          return;
        }
        if (decision === 'fallback') {
          startPolling();
          return;
        }
        setState('reconnecting');
        reconnectTimer = setTimeout(
          () => connectSse(attempt + 1),
          backoffMs(attempt, initialBackoffMs, maxBackoffMs),
        );
      }
    })();
  };

  const connectWs = (attempt: number) => {
    if (stopReconnect()) {
      return;
    }
    if (typeof WebSocket === 'undefined') {
      connectSse(0);
      return;
    }
    transport = 'ws';
    setState(attempt === 0 ? 'connecting' : 'reconnecting');

    void eventsUrl(jobId, true).then((httpUrl) => {
      if (stopReconnect()) {
        return;
      }
      try {
        socket = new WebSocket(httpToWsUrl(httpUrl));
      } catch {
        connectSse(0);
        return;
      }

      socket.onopen = () => {
        if (!closed) {
          setState('live');
        }
      };

      socket.onmessage = (message) => {
        const parsed = parseJobEvent(message.data);
        if (parsed) {
          deliverEvent(parsed);
        }
      };

      socket.onerror = () => {
        // onclose trata a reconexão
      };

      socket.onclose = () => {
        socket = null;
        if (stopReconnect()) {
          setState('closed');
          return;
        }
        const decision = shouldAttemptReconnect({
          closed,
          terminalReached,
          attempt,
          maxAttempts: wsMaxAttempts,
        });
        if (decision === 'stop') {
          setState('closed');
          return;
        }
        if (decision === 'fallback') {
          connectSse(0);
          return;
        }
        setState('reconnecting');
        reconnectTimer = setTimeout(
          () => connectWs(attempt + 1),
          backoffMs(attempt, initialBackoffMs, maxBackoffMs),
        );
      };
    });
  };

  connectWs(0);

  return () => {
    closed = true;
    clearTimers();
    if (socket) {
      socket.close();
      socket = null;
    }
    abortSse?.abort();
    abortSse = null;
    setState('closed');
  };
}
