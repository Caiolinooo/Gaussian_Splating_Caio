import { normalizeProgress } from './eventParse';
import type { JobState, PipelineStage, StageProgress, StageStatus, UiStage } from './types';

export const PIPELINE_STAGES: readonly PipelineStage[] = [
  'extracting',
  'sfm',
  'training',
  'exporting',
  'meshproxy',
  'autocal',
];

export const UI_STAGES: readonly UiStage[] = ['upload', ...PIPELINE_STAGES];

export interface TimelineItem {
  key: UiStage;
  label: string;
  status: StageStatus | 'upload-done';
  progress: number;
  detail?: string;
}

export function stageLabel(stage: UiStage): string {
  switch (stage) {
    case 'upload':
      return 'Envio';
    case 'extracting':
      return 'Extração de frames';
    case 'sfm':
      return 'Reconstrução (SfM)';
    case 'training':
      return 'Treino 3DGS';
    case 'exporting':
      return 'Exportação';
    case 'meshproxy':
      return 'Malha proxy';
    case 'autocal':
      return 'Auto-calibração';
    default: {
      const exhaustive: never = stage;
      throw new Error(`Etapa não tratada: ${String(exhaustive)}`);
    }
  }
}

export function jobStateLabel(state: JobState): string {
  switch (state) {
    case 'queued':
      return 'Na fila';
    case 'extracting':
      return 'Extraindo frames';
    case 'sfm':
      return 'Reconstruindo (SfM)';
    case 'training':
      return 'Treinando';
    case 'exporting':
      return 'Exportando';
    case 'meshproxy':
      return 'Gerando malha proxy';
    case 'autocal':
      return 'Calibrando escala';
    case 'done':
      return 'Concluído';
    case 'error':
      return 'Erro';
    case 'cancelled':
      return 'Cancelado';
    default: {
      const exhaustive: never = state;
      throw new Error(`Estado de job não tratado: ${String(exhaustive)}`);
    }
  }
}

export function stageStatusLabel(status: StageStatus): string {
  switch (status) {
    case 'pending':
      return 'Pendente';
    case 'running':
      return 'Em execução';
    case 'done':
      return 'Concluída';
    case 'failed':
      return 'Falhou';
    case 'skipped':
      return 'Pulada';
    default: {
      const exhaustive: never = status;
      throw new Error(`Status de etapa não tratado: ${String(exhaustive)}`);
    }
  }
}

export function sourceKindLabel(kind: 'video' | 'images'): string {
  switch (kind) {
    case 'video':
      return 'Vídeo';
    case 'images':
      return 'Imagens';
    default: {
      const exhaustive: never = kind;
      throw new Error(`Tipo de origem não tratado: ${String(exhaustive)}`);
    }
  }
}

export function estimateEtaSeconds(elapsedMs: number, overallProgress: number): number | null {
  const progress = normalizeProgress(overallProgress);
  if (elapsedMs <= 0 || progress <= 0.01 || progress >= 1) {
    return progress >= 1 ? 0 : null;
  }
  const remaining = (elapsedMs * (1 - progress)) / progress;
  return Math.round(remaining / 1000);
}

export function formatEta(seconds: number | null): string {
  if (seconds === null) {
    return 'Calculando…';
  }
  if (seconds <= 0) {
    return 'Concluído';
  }
  if (seconds < 60) {
    return `cerca de ${seconds} s`;
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `cerca de ${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `cerca de ${hours} h` : `cerca de ${hours} h ${rest} min`;
}

export function asDisplayPercent(progress: number): number {
  return Math.round(normalizeProgress(progress) * 100);
}

export function buildTimeline(
  stages: Partial<Record<PipelineStage, StageProgress>>,
  jobState: JobState,
  sourceKind?: 'video' | 'images',
): TimelineItem[] {
  const upload: TimelineItem = {
    key: 'upload',
    label: stageLabel('upload'),
    status: 'upload-done',
    progress: 1,
    detail: 'Arquivos recebidos.',
  };

  const rest: TimelineItem[] = PIPELINE_STAGES.map((key) => {
    const record = stages[key];
    let status: StageStatus = record?.status ?? 'pending';
    if (!record && sourceKind === 'images' && key === 'extracting') {
      status = 'skipped';
    }
    if (!record && jobState === 'done') {
      status = key === 'extracting' && sourceKind === 'images' ? 'skipped' : 'done';
    }
    const progress = normalizeProgress(
      record?.progress ?? (status === 'done' || status === 'skipped' ? 1 : 0),
    );
    let detail = record?.message ?? undefined;
    if (status === 'skipped' && key === 'extracting') {
      detail = detail ?? 'Conjunto de imagens — extração de frames não é necessária.';
    }
    return {
      key,
      label: stageLabel(key),
      status,
      progress,
      detail,
    };
  });

  return [upload, ...rest];
}

export function isTerminalState(state: JobState): boolean {
  switch (state) {
    case 'done':
    case 'error':
    case 'cancelled':
      return true;
    case 'queued':
    case 'extracting':
    case 'sfm':
    case 'training':
    case 'exporting':
    case 'meshproxy':
    case 'autocal':
      return false;
    default: {
      const exhaustive: never = state;
      throw new Error(`Estado de job não tratado: ${String(exhaustive)}`);
    }
  }
}
