import type { BackendDetection, RelightJson, SplatQuality, TemporalJson } from '@gs/viewer';
import { DEFAULT_RELIGHT, DEFAULT_SPLAT_QUALITY, DEFAULT_TEMPORAL } from '@gs/viewer';
import { create } from 'zustand';

import type { CameraPreset, WorkspaceTool } from '../types';

export type LoadPhase = 'idle' | 'scene' | 'artifact' | 'splat' | 'ready' | 'error';

export interface ViewerStore {
  jobId: string | null;
  sceneId: string | null;
  sceneName: string;
  loadPhase: LoadPhase;
  loadRatio: number;
  loadLabel: string;
  error: string | null;
  fps: number;
  gaussianCount: number;
  memoryMb: number | null;
  backend: BackendDetection | null;
  quality: SplatQuality;
  cameraPreset: CameraPreset;
  workspaceTool: WorkspaceTool;
  dirty: boolean;
  saving: boolean;
  lastSavedAt: number | null;
  temporal: TemporalJson;
  relight: RelightJson;
  setIds: (ids: { jobId?: string | null; sceneId?: string | null }) => void;
  setSceneName: (name: string) => void;
  setLoad: (phase: LoadPhase, ratio?: number, label?: string) => void;
  setError: (error: string | null) => void;
  setHud: (patch: { fps?: number; gaussianCount?: number; memoryMb?: number | null }) => void;
  setBackend: (backend: BackendDetection | null) => void;
  setQuality: (quality: Partial<SplatQuality>) => void;
  setCameraPreset: (preset: CameraPreset) => void;
  setWorkspaceTool: (tool: WorkspaceTool) => void;
  markDirty: (dirty?: boolean) => void;
  setSaving: (saving: boolean) => void;
  markSaved: () => void;
  setTemporal: (temporal: TemporalJson) => void;
  setRelight: (relight: RelightJson) => void;
}

export const useViewerStore = create<ViewerStore>((set) => ({
  jobId: null,
  sceneId: null,
  sceneName: 'Cena sem título',
  loadPhase: 'idle',
  loadRatio: 0,
  loadLabel: '',
  error: null,
  fps: 0,
  gaussianCount: 0,
  memoryMb: null,
  backend: null,
  quality: { ...DEFAULT_SPLAT_QUALITY },
  cameraPreset: 'iso',
  workspaceTool: 'orbit',
  dirty: false,
  saving: false,
  lastSavedAt: null,
  temporal: { ...DEFAULT_TEMPORAL },
  relight: { ...DEFAULT_RELIGHT },

  setIds(ids) {
    set((state) => ({
      jobId: ids.jobId === undefined ? state.jobId : ids.jobId,
      sceneId: ids.sceneId === undefined ? state.sceneId : ids.sceneId,
    }));
  },
  setSceneName(name) {
    set({ sceneName: name });
  },
  setLoad(phase, ratio = 0, label = '') {
    set((state) => ({
      loadPhase: phase,
      loadRatio: ratio,
      loadLabel: label,
      error: phase === 'error' ? state.error : null,
    }));
  },
  setError(error) {
    set({ error, loadPhase: error ? 'error' : 'idle' });
  },
  setHud(patch) {
    set(patch);
  },
  setBackend(backend) {
    set({ backend });
  },
  setQuality(quality) {
    set((state) => ({ quality: { ...state.quality, ...quality } }));
  },
  setCameraPreset(preset) {
    set({ cameraPreset: preset });
  },
  setWorkspaceTool(tool) {
    set({ workspaceTool: tool });
  },
  markDirty(dirty = true) {
    set({ dirty });
  },
  setSaving(saving) {
    set({ saving });
  },
  markSaved() {
    set({ dirty: false, saving: false, lastSavedAt: Date.now() });
  },
  setTemporal(temporal) {
    set({ temporal });
  },
  setRelight(relight) {
    set({ relight });
  },
}));
