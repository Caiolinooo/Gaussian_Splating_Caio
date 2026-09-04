import type { OutlinerItem, SnapSettings, TransformMode, TransformSpace } from '@gs/viewer';
import { DEFAULT_SNAP } from '@gs/viewer';
import { create } from 'zustand';

export interface LiveBbox {
  x: number;
  y: number;
  z: number;
}

export interface EditingStore {
  selectedNodeId: string | null;
  transformMode: TransformMode;
  transformSpace: TransformSpace;
  snap: SnapSettings;
  snapEnabled: boolean;
  items: OutlinerItem[];
  canUndo: boolean;
  canRedo: boolean;
  dragging: boolean;
  liveBbox: LiveBbox | null;
  liveTrs: {
    px: number;
    py: number;
    pz: number;
    rx: number;
    ry: number;
    rz: number;
    sx: number;
    sy: number;
    sz: number;
  } | null;
  select: (id: string | null) => void;
  setTransformMode: (mode: TransformMode) => void;
  setTransformSpace: (space: TransformSpace) => void;
  setSnap: (snap: Partial<SnapSettings>) => void;
  setSnapEnabled: (enabled: boolean) => void;
  setOutliner: (items: OutlinerItem[]) => void;
  setHistory: (canUndo: boolean, canRedo: boolean) => void;
  setDragging: (dragging: boolean) => void;
  setLiveBbox: (bbox: LiveBbox | null) => void;
  setLiveTrs: (trs: EditingStore['liveTrs']) => void;
}

export const useEditingStore = create<EditingStore>((set) => ({
  selectedNodeId: null,
  transformMode: 'translate',
  transformSpace: 'world',
  snap: { ...DEFAULT_SNAP },
  snapEnabled: true,
  items: [],
  canUndo: false,
  canRedo: false,
  dragging: false,
  liveBbox: null,
  liveTrs: null,

  select(id) {
    set({ selectedNodeId: id });
  },
  setTransformMode(mode) {
    set({ transformMode: mode });
  },
  setTransformSpace(space) {
    set({ transformSpace: space });
  },
  setSnap(snap) {
    set((state) => ({ snap: { ...state.snap, ...snap } }));
  },
  setSnapEnabled(enabled) {
    set({ snapEnabled: enabled });
  },
  setOutliner(items) {
    set({ items });
  },
  setHistory(canUndo, canRedo) {
    set({ canUndo, canRedo });
  },
  setDragging(dragging) {
    set({ dragging });
  },
  setLiveBbox(bbox) {
    set({ liveBbox: bbox });
  },
  setLiveTrs(trs) {
    set({ liveTrs: trs });
  },
}));
