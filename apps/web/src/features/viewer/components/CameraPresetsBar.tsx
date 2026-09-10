import { cameraPresetLabel } from '../runtime/cameraPresets';
import { useViewerRuntime } from '../runtime/ViewerRuntimeContext';
import { useViewerStore } from '../store/viewerStore';
import type { CameraPreset } from '../types';

const PRESETS: CameraPreset[] = ['front', 'side', 'top', 'iso'];

export function CameraPresetsBar() {
  const controller = useViewerRuntime();
  const active = useViewerStore((state) => state.cameraPreset);

  return (
    <div className="gs-presets" role="group" aria-label="Presets de câmera">
      <button type="button" onClick={() => controller?.frameFromCapture()}>
        Captura
      </button>
      <button type="button" onClick={() => controller?.fitToSplat()}>
        Enquadrar
      </button>
      {PRESETS.map((preset) => (
        <button
          key={preset}
          type="button"
          className={preset === active ? 'primary' : undefined}
          onClick={() => controller?.setCameraPreset(preset)}
        >
          {cameraPresetLabel(preset)}
        </button>
      ))}
    </div>
  );
}
