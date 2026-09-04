import { useViewerStore } from '../store/viewerStore';

export function LoadProgress() {
  const phase = useViewerStore((state) => state.loadPhase);
  const ratio = useViewerStore((state) => state.loadRatio);
  const label = useViewerStore((state) => state.loadLabel);
  const error = useViewerStore((state) => state.error);

  if (phase === 'ready' && !error) {
    return null;
  }
  if (phase === 'idle' && !error) {
    return null;
  }

  const percent = Math.round(Math.min(1, Math.max(0, ratio)) * 100);

  return (
    <div className="gs-load" role="status" aria-live="polite">
      {error ? (
        <p className="gs-load-error">{error}</p>
      ) : (
        <>
          <p>{label || 'Carregando…'}</p>
          <div
            className="progress-bar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
          >
            <div className="progress-bar-fill" style={{ width: `${percent}%` }} />
          </div>
          <span className="gs-load-pct">{percent}%</span>
        </>
      )}
    </div>
  );
}
