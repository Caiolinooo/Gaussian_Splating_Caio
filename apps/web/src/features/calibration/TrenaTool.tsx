import { useState } from 'react';

import { formatMeters } from '../../lib/unitsBinding';
import { useViewerRuntime } from '../viewer/runtime/ViewerRuntimeContext';
import { distance3 } from './math/tapeMath';
import { isCalibrated, metersFromScene, rootScaleFromCalibration } from './math/scaleFactor';
import { useCalibrationStore } from './store/calibrationStore';
import { useTapeStore } from './store/tapeStore';

export function TrenaTool() {
  const controller = useViewerRuntime();
  const active = useTapeStore((state) => state.active);
  const measures = useTapeStore((state) => state.measures);
  const draft = useTapeStore((state) => state.draft);
  const selectedId = useTapeStore((state) => state.selectedId);
  const referenceOpen = useTapeStore((state) => state.referenceOpen);
  const calibration = useCalibrationStore((state) => state.calibration);
  const unit = useCalibrationStore((state) => state.unitPref.unit);
  const [realValue, setRealValue] = useState('');

  const factor = rootScaleFromCalibration(calibration);
  const selected = measures.find((item) => item.id === selectedId) ?? null;

  return (
    <section className="gs-panel gs-trena" aria-labelledby="gs-trena-title">
      <header className="gs-panel-head">
        <h2 id="gs-trena-title">Trena</h2>
        <button
          type="button"
          className={active ? 'primary' : undefined}
          onClick={() => useTapeStore.getState().toggleActive()}
          title="Atalho: T"
        >
          {active ? 'Trena ligada' : 'Medir'}
        </button>
      </header>
      <p className="muted">
        {active
          ? draft
            ? 'Clique o segundo ponto. Arraste as esferas para ajustar.'
            : 'Clique dois pontos na cena. Atalho T liga/desliga.'
          : 'Ferramenta sempre disponível — não é um passo separado de setup.'}
      </p>
      <ul className="gs-trena-list">
        {measures.map((measure, index) => {
          const scene = distance3(measure.a, measure.b);
          const meters = isCalibrated(calibration) ? metersFromScene(scene, factor) : scene;
          const label = isCalibrated(calibration)
            ? formatMeters(meters, unit)
            : `${scene.toFixed(3)} u`;
          return (
            <li key={measure.id} className={measure.id === selectedId ? 'is-selected' : undefined}>
              <button type="button" onClick={() => useTapeStore.getState().select(measure.id)}>
                #{index + 1} · {label}
              </button>
              <button
                type="button"
                onClick={() => useTapeStore.getState().remove(measure.id)}
                aria-label="Excluir medida"
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>
      {selected && (
        <div className="gs-trena-ref">
          <button
            type="button"
            className="primary"
            onClick={() => useTapeStore.getState().setReferenceOpen(true)}
          >
            Usar como referência
          </button>
          {referenceOpen && (
            <label className="gs-field">
              Comprimento real ({unit})
              <input
                type="text"
                inputMode="decimal"
                value={realValue}
                onChange={(event) => setRealValue(event.target.value)}
              />
              <button
                type="button"
                onClick={() => {
                  const parsed = Number(realValue.replace(',', '.'));
                  if (Number.isFinite(parsed) && parsed > 0) {
                    controller?.applyManualReference(selected.id, parsed, unit);
                    setRealValue('');
                  }
                }}
              >
                Recalcular escala
              </button>
            </label>
          )}
        </div>
      )}
    </section>
  );
}
