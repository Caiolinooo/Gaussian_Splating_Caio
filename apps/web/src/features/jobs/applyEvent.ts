import type { JobEvent } from './eventParse';
import { PIPELINE_STAGES, isTerminalState } from './stages';
import type { JobDetail, PipelineStage, StageProgress } from './types';

function eventErrorCode(event: JobEvent, fallback: string | null): string | null {
  const fromMetrics = event.metrics.error_code;
  if (typeof fromMetrics === 'string' && fromMetrics.trim()) {
    return fromMetrics;
  }
  return fallback;
}

export function markPriorStagesDone(
  stages: Partial<Record<PipelineStage, StageProgress>>,
  currentStage: JobEvent['stage'],
): Partial<Record<PipelineStage, StageProgress>> {
  if (!currentStage || currentStage === 'upload') {
    return stages;
  }
  const index = PIPELINE_STAGES.indexOf(currentStage);
  if (index <= 0) {
    return stages;
  }
  const next = { ...stages };
  for (let i = 0; i < index; i += 1) {
    const key = PIPELINE_STAGES[i];
    const previous = next[key];
    if (!previous) {
      continue;
    }
    if (previous.status === 'skipped' || previous.status === 'failed') {
      continue;
    }
    if (previous.status === 'done') {
      if ((previous.progress ?? 0) < 1) {
        next[key] = { ...previous, progress: 1 };
      }
      continue;
    }
    next[key] = { ...previous, status: 'done', progress: 1 };
  }
  return next;
}

export function applyJobEvent(current: JobDetail | null, event: JobEvent): JobDetail | null {
  if (!current) {
    return current;
  }
  const stages = markPriorStagesDone({ ...current.stages }, event.stage);
  if (event.stage && event.stage !== 'upload') {
    const previous = stages[event.stage];
    const failed = event.state === 'error' && previous?.status !== 'done';
    stages[event.stage] = {
      status: failed ? 'failed' : 'running',
      progress: event.stage_progress,
      message: event.message || previous?.message,
    };
    if (event.state === 'done') {
      stages[event.stage] = { ...stages[event.stage]!, status: 'done', progress: 1 };
    }
  }
  const terminal = isTerminalState(event.state);
  return {
    ...current,
    state: event.state,
    stages,
    eta_seconds: terminal ? 0 : (event.metrics.eta_seconds ?? current.eta_seconds),
    error_code:
      event.state === 'error' ? eventErrorCode(event, current.error_code) : current.error_code,
    error_message:
      event.state === 'error' ? event.message || current.error_message : current.error_message,
  };
}
