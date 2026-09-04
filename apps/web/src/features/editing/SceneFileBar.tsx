import { useRef, useState } from 'react';

import { isCalibrated } from '../calibration/math/scaleFactor';
import { useCalibrationStore } from '../calibration/store/calibrationStore';
import { useViewerRuntime } from '../viewer/runtime/ViewerRuntimeContext';
import { useViewerStore } from '../viewer/store/viewerStore';

export function SceneFileBar() {
  const controller = useViewerRuntime();
  const dirty = useViewerStore((state) => state.dirty);
  const saving = useViewerStore((state) => state.saving);
  const sceneId = useViewerStore((state) => state.sceneId);
  const sceneName = useViewerStore((state) => state.sceneName);
  const calibrated = useCalibrationStore((state) => isCalibrated(state.calibration));
  const fileRef = useRef<HTMLInputElement>(null);
  const [openId, setOpenId] = useState(sceneId ?? '');

  return (
    <div className="gs-filebar">
      <strong>{sceneName}</strong>
      {dirty && <span className="gs-dirty">não salvo</span>}
      <button
        type="button"
        className="primary"
        disabled={saving}
        onClick={() => void controller?.saveScene()}
      >
        {saving ? 'Salvando…' : 'Salvar cena'}
      </button>
      <label className="gs-inline">
        Abrir
        <input
          value={openId}
          onChange={(event) => setOpenId(event.target.value)}
          placeholder="id da cena"
        />
        <button
          type="button"
          disabled={!openId.trim()}
          onClick={() => void controller?.openSceneById(openId.trim())}
        >
          Carregar
        </button>
      </label>
      <input
        ref={fileRef}
        type="file"
        accept=".glb,.gltf"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) {
            void controller?.importGlb(file);
          }
          event.target.value = '';
        }}
      />
      <button
        type="button"
        disabled={!calibrated}
        title={calibrated ? 'Importar GLB' : 'Calibre a cena antes de inserir objetos'}
        onClick={() => fileRef.current?.click()}
      >
        Importar GLB
      </button>
    </div>
  );
}
