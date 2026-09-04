import { overlayKindLabelPt } from './overlayPersist';
import { useOverlayStore } from './store/overlayStore';
import { useViewerRuntime } from '../viewer/runtime/ViewerRuntimeContext';

export function OverlayList() {
  const controller = useViewerRuntime();
  const overlays = useOverlayStore((state) => state.overlays);
  const selectedId = useOverlayStore((state) => state.selectedId);

  if (overlays.length === 0) {
    return <p className="muted">Nenhum overlay aplicado.</p>;
  }

  return (
    <ul className="gs-overlay-list">
      {overlays.map((overlay) => (
        <li key={overlay.id} className={overlay.id === selectedId ? 'is-selected' : undefined}>
          <button type="button" onClick={() => useOverlayStore.getState().select(overlay.id)}>
            {overlayKindLabelPt(overlay.kind)} · {Math.round(overlay.opacity * 100)}%
          </button>
          <button
            type="button"
            onClick={() => controller?.removeOverlay(overlay.id)}
            aria-label="Remover overlay"
          >
            ×
          </button>
        </li>
      ))}
    </ul>
  );
}
