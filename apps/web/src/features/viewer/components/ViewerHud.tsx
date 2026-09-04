import type { DetectedBackendKind } from '@gs/viewer';

import { CalibrationIndicator } from '../../calibration/CalibrationIndicator';
import { assertNever } from '../assertNever';
import { useViewerRuntime } from '../runtime/ViewerRuntimeContext';
import { useViewerStore } from '../store/viewerStore';

export function ViewerHud() {
  const controller = useViewerRuntime();
  const fps = useViewerStore((state) => state.fps);
  const gaussians = useViewerStore((state) => state.gaussianCount);
  const backend = useViewerStore((state) => state.backend);
  const quality = useViewerStore((state) => state.quality);
  const memoryMb = useViewerStore((state) => state.memoryMb);

  const badge = backendBadge(backend?.backend ?? 'none');

  return (
    <div className="gs-hud" aria-label="Informações do viewer">
      <span>{Math.round(fps)} FPS</span>
      <span>{gaussians.toLocaleString('pt-BR')} gaussianas</span>
      <span className={`gs-badge gs-badge-${badge.tone}`} title={backend?.reason ?? ''}>
        {badge.label}
      </span>
      <button
        type="button"
        onClick={() => controller?.cycleShDegree()}
        title="Alternar grau de spherical harmonics"
      >
        SH {quality.shDegree}
      </button>
      {memoryMb !== null && <span>{memoryMb.toFixed(0)} MB</span>}
      <CalibrationIndicator />
    </div>
  );
}

function backendBadge(kind: DetectedBackendKind): {
  label: string;
  tone: 'spark' | 'webgl' | 'none';
} {
  switch (kind) {
    case 'spark':
      return { label: 'Spark', tone: 'spark' };
    case 'mkkellogg':
      return { label: 'WebGL2', tone: 'webgl' };
    case 'none':
      return { label: '—', tone: 'none' };
    default:
      return assertNever(kind);
  }
}
