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
  const temporal = useViewerStore((state) => state.temporal);
  const relight = useViewerStore((state) => state.relight);

  const badge = backendBadge(backend?.backend ?? 'none', backend?.webgpu === true);

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
      {temporal.enabled && (
        <label className="gs-scrubber">
          Tempo
          <input
            type="range"
            min={0}
            max={1000}
            value={Math.round(temporal.currentTime * 1000)}
            aria-label="Scrubber temporal"
            onChange={(event) => controller?.setPlaybackTime(Number(event.target.value) / 1000)}
          />
          <span>
            {temporal.frameCount > 0
              ? `${Math.round(temporal.currentTime * Math.max(temporal.frameCount - 1, 0)) + 1}/${temporal.frameCount}`
              : `${Math.round(temporal.currentTime * 100)}%`}
          </span>
        </label>
      )}
      <label className="gs-relight" title="Contrato futuro — treino 4DGS/relight ainda não existe">
        <input
          type="checkbox"
          checked={relight.enabled}
          disabled={relight.mode === 'unsupported'}
          onChange={(event) => controller?.setRelightPreview(event.target.checked)}
        />
        Relight ({relight.mode})
      </label>
      <CalibrationIndicator />
    </div>
  );
}

function backendBadge(
  kind: DetectedBackendKind,
  webgpu: boolean,
): {
  label: string;
  tone: 'spark' | 'webgl' | 'none';
} {
  switch (kind) {
    case 'spark':
      return { label: webgpu ? 'Spark · WebGPU' : 'Spark', tone: 'spark' };
    case 'mkkellogg':
      return { label: 'WebGL2', tone: 'webgl' };
    case 'none':
      return { label: '—', tone: 'none' };
    default:
      return assertNever(kind);
  }
}
