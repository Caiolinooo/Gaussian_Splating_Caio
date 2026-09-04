import { createStore, type StoreApi } from 'zustand/vanilla';
import { immer } from 'zustand/middleware/immer';

import type { BackendDetection } from '../renderer/detectBackend';
import {
  DEFAULT_SNAP,
  type SnapSettings,
  type TransformMode,
  type TransformSpace,
} from './TransformGizmo';

export interface ViewerUiState {
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  transformMode: TransformMode;
  transformSpace: TransformSpace;
  snap: SnapSettings;
  backend: BackendDetection | null;
  playing: boolean;
}

export interface ViewerUiActions {
  select(id: string | null): void;
  hover(id: string | null): void;
  setTransformMode(mode: TransformMode): void;
  setTransformSpace(space: TransformSpace): void;
  setSnap(snap: Partial<SnapSettings>): void;
  setBackend(detection: BackendDetection | null): void;
  setPlaying(playing: boolean): void;
}

export type ViewerUiStore = ViewerUiState & ViewerUiActions;

const initialState: ViewerUiState = {
  selectedNodeId: null,
  hoveredNodeId: null,
  transformMode: 'translate',
  transformSpace: 'world',
  snap: { ...DEFAULT_SNAP },
  backend: null,
  playing: false,
};

/** Store Zustand (vanilla + immer) para estado efêmero da UI do viewer. */
export function createViewerUiStore(seed: Partial<ViewerUiState> = {}): StoreApi<ViewerUiStore> {
  return createStore<ViewerUiStore>()(
    immer((set) => ({
      ...initialState,
      ...seed,
      snap: { ...DEFAULT_SNAP, ...seed.snap },
      select(id) {
        set((state) => {
          state.selectedNodeId = id;
        });
      },
      hover(id) {
        set((state) => {
          state.hoveredNodeId = id;
        });
      },
      setTransformMode(mode) {
        set((state) => {
          state.transformMode = mode;
        });
      },
      setTransformSpace(space) {
        set((state) => {
          state.transformSpace = space;
        });
      },
      setSnap(snap) {
        set((state) => {
          state.snap = { ...state.snap, ...snap };
        });
      },
      setBackend(detection) {
        set((state) => {
          state.backend = detection;
        });
      },
      setPlaying(playing) {
        set((state) => {
          state.playing = playing;
        });
      },
    })),
  );
}
