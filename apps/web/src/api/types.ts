/** Tipos espelhando os schemas da API (apps/api). */

export type CheckStatus = 'ok' | 'warning' | 'error' | 'missing' | 'unknown';

export interface ComponentCheck {
  key: string;
  name: string;
  status: CheckStatus;
  message: string;
  details: Record<string, unknown>;
  fix_hint: string | null;
}

export interface HealthReport {
  checks: ComponentCheck[];
  overall: CheckStatus;
  ready: boolean;
  generated_at: string;
}

export type StepStatus = 'pending' | 'running' | 'done' | 'skipped' | 'error';

export type SetupState = 'idle' | 'running' | 'done' | 'error';

export interface SetupStep {
  key: string;
  title: string;
  status: StepStatus;
  detail: string | null;
}

export interface SetupProgress {
  state: SetupState;
  percent: number;
  steps: SetupStep[];
  log: string[];
  updated_at: string;
}

export interface ApiHealth {
  status: string;
  service: string;
  version: string;
}

export interface InstallAccepted {
  state: string;
  message: string;
}
