import type { DetectedBackendKind } from '@gs/viewer';

import { CalibrationIndicator } from '../../calibration/CalibrationIndicator';
import { assertNever } from '../assertNever';
import { useViewerRuntime } from '../runtime/ViewerRuntimeContext';
import { useViewerStore } from '../store/viewerStore';
import { SharpnessControls } from './SharpnessControls';
import { useState } from 'react';

export function ViewerHud() {
  const controller = useViewerRuntime();
  const fps = useViewerStore((state) => state.fps);
  const gaussians = useViewerStore((state) => state.gaussianCount);
  const backend = useViewerStore((state) => state.backend);
  const quality = useViewerStore((state) => state.quality);
  const memoryMb = useViewerStore((state) => state.memoryMb);
  const temporal = useViewerStore((state) => state.temporal);
  const relight = useViewerStore((state) => state.relight);
  const [showSharpness, setShowSharpness] = useState(false);

  const badge = backendBadge(backend?.backend ?? 'none', backend?.webgpu === true);
  const azimuth = relight.azimuthDeg ?? 45;
  const elevation = relight.elevationDeg ?? 35;
  const intensity = relight.intensity ?? 1;

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
      <button type="button" onClick={() => controller?.fitToSplat()}>
        Enquadrar
      </button>
      <button
        type="button"
        onClick={() => setShowSharpness((value) => !value)}
        aria-expanded={showSharpness}
        title="Controles de nitidez (anti-smearing)"
      >
        Nitidez
      </button>
      {memoryMb !== null && <span>{memoryMb.toFixed(0)} MB</span>}
      {showSharpness && <SharpnessControls quality={quality} />}
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
      <label className="gs-relight">
        <input
          type="checkbox"
          checked={relight.enabled}
          aria-label="Relight"
          onChange={(event) => controller?.setRelightPreview(event.target.checked)}
        />
        Relight ({relight.mode})
      </label>
      <label className="gs-relight">
        Azimute
        <input
          type="range"
          min={0}
          max={360}
          value={Math.round(azimuth)}
          aria-label="Azimute do relight"
          onChange={(event) => controller?.setRelightEnv({ azimuthDeg: Number(event.target.value) })}
        />
      </label>
      <label className="gs-relight">
        Elevação
        <input
          type="range"
          min={-10}
          max={89}
          value={Math.round(elevation)}
          aria-label="Elevação do relight"
          onChange={(event) =>
            controller?.setRelightEnv({ elevationDeg: Number(event.target.value) })
          }
        />
      </label>
      <label className="gs-relight">
        Intensidade
        <input
          type="range"
          min={0}
          max={200}
          value={Math.round(intensity * 100)}
          aria-label="Intensidade do relight"
          onChange={(event) =>
            controller?.setRelightEnv({ intensity: Number(event.target.value) / 100 })
          }
        />
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
