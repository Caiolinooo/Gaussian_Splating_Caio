import { describe, expect, it } from 'vitest';

import {
  httpToWsUrl,
  isJobState,
  normalizeProgress,
  parseJobEvent,
  shouldAttemptReconnect,
} from '../eventParse';

describe('parseJobEvent', () => {
  it('aceita o contrato WS/SSE', () => {
    const event = parseJobEvent({
      state: 'training',
      stage: 'training',
      stage_progress: 0.4,
      overall_progress: 0.55,
      message: 'step 4000/10000',
      metrics: { psnr: 24.1 },
    });
    expect(event).toEqual({
      state: 'training',
      stage: 'training',
      stage_progress: 0.4,
      overall_progress: 0.55,
      message: 'step 4000/10000',
      metrics: { psnr: 24.1 },
    });
  });

  it('normaliza progresso em porcentagem 0–100', () => {
    const event = parseJobEvent({
      state: 'sfm',
      stage: 'sfm',
      stage_progress: 80,
      overall_progress: 25,
      message: '',
    });
    expect(event?.stage_progress).toBe(0.8);
    expect(event?.overall_progress).toBe(0.25);
  });

  it('lê envelope SSE data:', () => {
    const event = parseJobEvent(
      'data: {"state":"done","stage":"autocal","stage_progress":1,"overall_progress":1,"message":"ok"}',
    );
    expect(event?.state).toBe('done');
    expect(event?.stage).toBe('autocal');
  });

  it('ignora payload sem state válido', () => {
    expect(parseJobEvent({ foo: 1 })).toBeNull();
    expect(parseJobEvent('')).toBeNull();
    expect(parseJobEvent('[DONE]')).toBeNull();
  });
});

describe('shouldAttemptReconnect', () => {
  it('para em estado terminal ou fechado', () => {
    expect(
      shouldAttemptReconnect({ closed: false, terminalReached: true, attempt: 0, maxAttempts: 5 }),
    ).toBe('stop');
    expect(
      shouldAttemptReconnect({ closed: true, terminalReached: false, attempt: 0, maxAttempts: 5 }),
    ).toBe('stop');
  });

  it('cai no fallback ao esgotar tentativas', () => {
    expect(
      shouldAttemptReconnect({ closed: false, terminalReached: false, attempt: 4, maxAttempts: 5 }),
    ).toBe('fallback');
    expect(
      shouldAttemptReconnect({ closed: false, terminalReached: false, attempt: 1, maxAttempts: 5 }),
    ).toBe('retry');
  });
});

describe('normalizeProgress / helpers', () => {
  it('satura fora do intervalo', () => {
    expect(normalizeProgress(-1)).toBe(0);
    expect(normalizeProgress(2)).toBe(0.02);
    expect(normalizeProgress(150)).toBe(1);
  });

  it('reconhece estados do contrato', () => {
    expect(isJobState('autocal')).toBe(true);
    expect(isJobState('upload')).toBe(false);
  });

  it('converte http(s) para ws(s)', () => {
    expect(httpToWsUrl('http://localhost:8000/jobs/1/events')).toBe(
      'ws://localhost:8000/jobs/1/events',
    );
    expect(httpToWsUrl('https://api.example/jobs/1/events')).toBe(
      'wss://api.example/jobs/1/events',
    );
  });
});
