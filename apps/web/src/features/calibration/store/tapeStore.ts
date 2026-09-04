import { create } from 'zustand';

import { clonePoint, type ScenePoint } from '../math/tapeMath';

export interface TapeMeasure {
  id: string;
  a: ScenePoint;
  b: ScenePoint;
}

export interface TapeDraft {
  a: ScenePoint;
}

export interface TapeStore {
  active: boolean;
  measures: TapeMeasure[];
  draft: TapeDraft | null;
  hover: ScenePoint | null;
  selectedId: string | null;
  dragging: { measureId: string; end: 'a' | 'b' } | null;
  referenceOpen: boolean;
  toggleActive: (force?: boolean) => void;
  beginDraft: (a: ScenePoint) => void;
  completeDraft: (b: ScenePoint) => TapeMeasure | null;
  setHover: (point: ScenePoint | null) => void;
  cancelDraft: () => void;
  updateEnd: (id: string, end: 'a' | 'b', point: ScenePoint) => void;
  remove: (id: string) => void;
  select: (id: string | null) => void;
  setDragging: (dragging: TapeStore['dragging']) => void;
  setReferenceOpen: (open: boolean) => void;
  clear: () => void;
}

function createMeasureId(): string {
  return `tape-${crypto.randomUUID()}`;
}

export const useTapeStore = create<TapeStore>((set, get) => ({
  active: false,
  measures: [],
  draft: null,
  hover: null,
  selectedId: null,
  dragging: null,
  referenceOpen: false,

  toggleActive(force) {
    const next = force ?? !get().active;
    set({
      active: next,
      draft: next ? get().draft : null,
    });
  },
  beginDraft(a) {
    set({ draft: { a: clonePoint(a) }, active: true });
  },
  completeDraft(b) {
    const draft = get().draft;
    if (!draft) {
      return null;
    }
    const measure: TapeMeasure = {
      id: createMeasureId(),
      a: clonePoint(draft.a),
      b: clonePoint(b),
    };
    set((state) => ({
      measures: [...state.measures, measure],
      draft: null,
      selectedId: measure.id,
    }));
    return measure;
  },
  setHover(point) {
    set({ hover: point ? clonePoint(point) : null });
  },
  cancelDraft() {
    set({ draft: null, hover: null });
  },
  updateEnd(id, end, point) {
    set((state) => ({
      measures: state.measures.map((item) =>
        item.id === id ? { ...item, [end]: clonePoint(point) } : item,
      ),
    }));
  },
  remove(id) {
    set((state) => ({
      measures: state.measures.filter((item) => item.id !== id),
      selectedId: state.selectedId === id ? null : state.selectedId,
      referenceOpen: state.selectedId === id ? false : state.referenceOpen,
    }));
  },
  select(id) {
    set({ selectedId: id });
  },
  setDragging(dragging) {
    set({ dragging });
  },
  setReferenceOpen(open) {
    set({ referenceOpen: open });
  },
  clear() {
    set({
      measures: [],
      draft: null,
      hover: null,
      selectedId: null,
      dragging: null,
      referenceOpen: false,
    });
  },
}));
