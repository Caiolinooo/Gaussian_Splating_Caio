import type {
  JobDetail,
  JobState,
  JobSummary,
  PipelineStage,
  SourceKind,
  StageProgress,
  StageStatus,
} from '../../lib/api';

export type {
  JobDetail,
  JobState,
  JobSummary,
  PipelineStage,
  SourceKind,
  StageProgress,
  StageStatus,
};

export type UiStage = 'upload' | PipelineStage;

export type HeightSystem = 'metric' | 'imperial';

export type UploadStep = 1 | 2;

export interface ExplainedError {
  code: string;
  title: string;
  message: string;
  action: string;
}

export const JOB_PATHS = {
  list: '/jobs',
  upload: '/upload',
  progress: (jobId: string) => `/jobs/${jobId}`,
  scene: (jobId: string) => `/viewer?job=${encodeURIComponent(jobId)}`,
} as const;

export const OPEN_SCENE_EVENT = 'gs:open-scene';

export interface OpenSceneDetail {
  jobId: string;
  sceneId?: string | null;
}
