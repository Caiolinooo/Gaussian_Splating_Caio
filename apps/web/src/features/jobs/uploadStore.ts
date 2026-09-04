import { create } from 'zustand';

import { ApiError, createJob } from '../../lib/api';
import { collectMediaErrors } from './mediaProbe';
import type { HeightSystem, SourceKind, UploadStep } from './types';
import {
  heightInputToMeters,
  metersToApiField,
  validateHeightMeters,
  type HeightInput,
} from './height';
import { validateFilesSync } from './validation';

export function createIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `idem-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

interface UploadStore {
  step: UploadStep;
  files: File[];
  sourceKind: SourceKind | null;
  fileErrors: string[];
  heightSystem: HeightSystem;
  metricMeters: string;
  metricCentimeters: string;
  imperialFeet: string;
  imperialInches: string;
  heightError: string | null;
  mediaProbing: boolean;
  submitting: boolean;
  uploadPercent: number;
  submitError: string | null;
  jobId: string | null;
  setFiles: (files: File[]) => void;
  removeFile: (index: number) => void;
  clearFiles: () => void;
  probeMedia: () => Promise<boolean>;
  goToStep: (step: UploadStep) => void;
  setHeightSystem: (system: HeightSystem) => void;
  setMetricMeters: (value: string) => void;
  setMetricCentimeters: (value: string) => void;
  setImperialFeet: (value: string) => void;
  setImperialInches: (value: string) => void;
  heightInput: () => HeightInput;
  submit: () => Promise<string | null>;
  reset: () => void;
}

const initialHeight = {
  heightSystem: 'metric' as HeightSystem,
  metricMeters: '',
  metricCentimeters: '',
  imperialFeet: '',
  imperialInches: '',
  heightError: null as string | null,
};

export const useUploadStore = create<UploadStore>((set, get) => ({
  step: 1,
  files: [],
  sourceKind: null,
  fileErrors: [],
  ...initialHeight,
  mediaProbing: false,
  submitting: false,
  uploadPercent: 0,
  submitError: null,
  jobId: null,

  setFiles: (files) => {
    const result = validateFilesSync(files);
    const kind = result.kind === 'video' || result.kind === 'images' ? result.kind : null;
    set({
      files,
      sourceKind: kind,
      fileErrors: result.errors,
      submitError: null,
      jobId: null,
      uploadPercent: 0,
    });
  },

  removeFile: (index) => {
    const next = get().files.filter((_, i) => i !== index);
    get().setFiles(next);
  },

  clearFiles: () => {
    get().setFiles([]);
  },

  probeMedia: async () => {
    const { files, sourceKind } = get();
    const sync = validateFilesSync(files);
    if (!sync.ok || (sync.kind !== 'video' && sync.kind !== 'images')) {
      set({ fileErrors: sync.errors, sourceKind: null });
      return false;
    }
    set({ mediaProbing: true, fileErrors: sync.errors, sourceKind: sync.kind });
    const mediaErrors = await collectMediaErrors(files, sourceKind ?? sync.kind);
    const all = [...sync.errors, ...mediaErrors];
    set({ mediaProbing: false, fileErrors: all, sourceKind: sync.kind });
    return all.length === 0;
  },

  goToStep: (step) => {
    set({ step, submitError: null });
  },

  setHeightSystem: (heightSystem) => set({ heightSystem, heightError: null }),
  setMetricMeters: (metricMeters) => set({ metricMeters, heightError: null }),
  setMetricCentimeters: (metricCentimeters) => set({ metricCentimeters, heightError: null }),
  setImperialFeet: (imperialFeet) => set({ imperialFeet, heightError: null }),
  setImperialInches: (imperialInches) => set({ imperialInches, heightError: null }),

  heightInput: () => {
    const state = get();
    if (state.heightSystem === 'metric') {
      return { system: 'metric', meters: state.metricMeters, centimeters: state.metricCentimeters };
    }
    return { system: 'imperial', feet: state.imperialFeet, inches: state.imperialInches };
  },

  submit: async () => {
    const state = get();
    if (!state.sourceKind || state.files.length === 0) {
      set({ submitError: 'Selecione os arquivos no passo anterior.', step: 1 });
      return null;
    }
    const meters = heightInputToMeters(state.heightInput());
    const heightError = validateHeightMeters(meters);
    if (heightError || meters === null) {
      set({ heightError: heightError, submitError: null });
      return null;
    }

    set({ submitting: true, submitError: null, uploadPercent: 0, heightError: null });
    const idempotencyKey = createIdempotencyKey();
    try {
      const created = await createJob({
        files: state.files,
        sourceKind: state.sourceKind,
        userHeightM: metersToApiField(meters),
        idempotencyKey,
        onUploadProgress: (uploadPercent) => set({ uploadPercent }),
      });
      set({ submitting: false, uploadPercent: 100, jobId: created.job_id });
      return created.job_id;
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Não foi possível enviar o job. Tente novamente.';
      set({ submitting: false, submitError: message });
      return null;
    }
  },

  reset: () => {
    set({
      step: 1,
      files: [],
      sourceKind: null,
      fileErrors: [],
      ...initialHeight,
      mediaProbing: false,
      submitting: false,
      uploadPercent: 0,
      submitError: null,
      jobId: null,
    });
  },
}));
