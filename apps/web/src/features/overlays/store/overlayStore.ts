import type { BlendMode, Overlay, OverlayKind, PhysicalSize } from '@gs/overlays';
import { create } from 'zustand';

export interface OverlayDraftState {
  kind: OverlayKind;
  imageUrl: string | null;
  imageName: string;
  color: string;
  opacity: number;
  blendMode: BlendMode;
  width: number;
  height: number;
  sizeUnit: PhysicalSize['width']['unit'];
  maskEnabled: boolean;
  placementMode: boolean;
}

const defaultDraft = (): OverlayDraftState => ({
  kind: 'sticker',
  imageUrl: null,
  imageName: '',
  color: '#4f46e5',
  opacity: 1,
  blendMode: 'normal',
  width: 30,
  height: 45,
  sizeUnit: 'cm',
  maskEnabled: true,
  placementMode: false,
});

export interface OverlayUiStore {
  overlays: Overlay[];
  selectedId: string | null;
  draft: OverlayDraftState;
  error: string | null;
  setOverlays: (overlays: Overlay[]) => void;
  select: (id: string | null) => void;
  patchDraft: (patch: Partial<OverlayDraftState>) => void;
  resetDraft: () => void;
  setError: (error: string | null) => void;
}

export const useOverlayStore = create<OverlayUiStore>((set) => ({
  overlays: [],
  selectedId: null,
  draft: defaultDraft(),
  error: null,

  setOverlays(overlays) {
    set({ overlays });
  },
  select(id) {
    set({ selectedId: id });
  },
  patchDraft(patch) {
    set((state) => ({ draft: { ...state.draft, ...patch } }));
  },
  resetDraft() {
    set((state) => {
      if (state.draft.imageUrl && state.draft.imageUrl.startsWith('blob:')) {
        URL.revokeObjectURL(state.draft.imageUrl);
      }
      return { draft: defaultDraft() };
    });
  },
  setError(error) {
    set({ error });
  },
}));
