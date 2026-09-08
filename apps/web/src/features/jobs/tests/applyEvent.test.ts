import { describe, expect, it } from 'vitest';

import { applyJobEvent, markPriorStagesDone } from '../applyEvent';
import type { JobEvent } from '../eventParse';
import type { JobDetail } from '../types';

function detail(partial: Partial<JobDetail> = {}): JobDetail {
  return {
    job_id: 'job-1',
    state: 'extracting',
    stages: {},
    error_code: null,
    error_message: null,
    eta_seconds: 120,
    ...partial,
  };
}

function event(partial: Partial<JobEvent> & Pick<JobEvent, 'state'>): JobEvent {
  return {
    stage: null,
    stage_progress: 0,
    overall_progress: 0,
    message: '',
    metrics: {},
    ...partial,
  };
}

describe('markPriorStagesDone', () => {
  it('marca extração em execução como concluída quando o SfM começa', () => {
    const next = markPriorStagesDone(
      { extracting: { status: 'running', progress: 1, message: 'pronto' } },
      'sfm',
    );
    expect(next.extracting).toEqual({ status: 'done', progress: 1, message: 'pronto' });
  });

  it('não cria etapa ausente nem sobrescreve skipped/failed', () => {
    const next = markPriorStagesDone({ extracting: { status: 'skipped', progress: 1 } }, 'sfm');
    expect(next.extracting?.status).toBe('skipped');
    expect(next.training).toBeUndefined();
  });
});

describe('applyJobEvent', () => {
  it('avança etapas anteriores quando uma posterior falha', () => {
    const current = detail({
      state: 'extracting',
      stages: {
        extracting: { status: 'running', progress: 1, message: '100%' },
      },
    });
    const next = applyJobEvent(
      current,
      event({
        state: 'error',
        stage: 'sfm',
        stage_progress: 0.2,
        message: 'COLMAP ausente',
        metrics: { error_code: 'COLMAP_FAILED' },
      }),
    );
    expect(next?.stages.extracting?.status).toBe('done');
    expect(next?.stages.sfm?.status).toBe('failed');
    expect(next?.state).toBe('error');
    expect(next?.error_code).toBe('COLMAP_FAILED');
    expect(next?.eta_seconds).toBe(0);
  });

  it('zera ETA em estados terminais', () => {
    const current = detail({ state: 'training', eta_seconds: 90 });
    const next = applyJobEvent(current, event({ state: 'cancelled' }));
    expect(next?.eta_seconds).toBe(0);
  });
});
