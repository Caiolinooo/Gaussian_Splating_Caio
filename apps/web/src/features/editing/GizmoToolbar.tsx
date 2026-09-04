import type { TransformMode, TransformSpace } from '@gs/viewer';

import { useViewerRuntime } from '../viewer/runtime/ViewerRuntimeContext';
import { useEditingStore } from './store/editingStore';

export function GizmoToolbar() {
  const controller = useViewerRuntime();
  const mode = useEditingStore((state) => state.transformMode);
  const space = useEditingStore((state) => state.transformSpace);
  const snapEnabled = useEditingStore((state) => state.snapEnabled);
  const canUndo = useEditingStore((state) => state.canUndo);
  const canRedo = useEditingStore((state) => state.canRedo);

  function setMode(next: TransformMode): void {
    useEditingStore.getState().setTransformMode(next);
  }

  function setSpace(next: TransformSpace): void {
    useEditingStore.getState().setTransformSpace(next);
  }

  return (
    <div className="gs-gizmo-bar" role="toolbar" aria-label="Gizmos de transformação">
      <button
        type="button"
        className={mode === 'translate' ? 'primary' : undefined}
        onClick={() => setMode('translate')}
      >
        Mover
      </button>
      <button
        type="button"
        className={mode === 'rotate' ? 'primary' : undefined}
        onClick={() => setMode('rotate')}
      >
        Girar
      </button>
      <button
        type="button"
        className={mode === 'scale' ? 'primary' : undefined}
        onClick={() => setMode('scale')}
      >
        Escalar
      </button>
      <button
        type="button"
        className={space === 'world' ? 'primary' : undefined}
        onClick={() => setSpace('world')}
      >
        Mundo
      </button>
      <button
        type="button"
        className={space === 'local' ? 'primary' : undefined}
        onClick={() => setSpace('local')}
      >
        Local
      </button>
      <button
        type="button"
        className={snapEnabled ? 'primary' : undefined}
        onClick={() => useEditingStore.getState().setSnapEnabled(!snapEnabled)}
      >
        Snap
      </button>
      <button type="button" disabled={!canUndo} onClick={() => controller?.undo()}>
        Desfazer
      </button>
      <button type="button" disabled={!canRedo} onClick={() => controller?.redo()}>
        Refazer
      </button>
    </div>
  );
}
