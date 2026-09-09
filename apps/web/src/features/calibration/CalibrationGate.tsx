import type { LengthUnit } from '@gs/viewer';
import { useState } from 'react';

import { formatMeters, toMeters } from '../../lib/unitsBinding';
import { assertNever } from '../viewer/assertNever';
import { useViewerRuntime } from '../viewer/runtime/ViewerRuntimeContext';
import { useViewerStore } from '../viewer/store/viewerStore';
import { useCalibrationStore } from './store/calibrationStore';

export function CalibrationGate() {
  const controller = useViewerRuntime();
  const phase = useCalibrationStore((state) => state.gatePhase);
  const unit = useCalibrationStore((state) => state.unitPref.unit);
  const loadPhase = useViewerStore((state) => state.loadPhase);
  const [adjustValue, setAdjustValue] = useState('');

  if (loadPhase === 'error') {
    return null;
  }

  switch (phase) {
    case 'hidden':
      return null;
    case 'blocked':
      return (
        <div className="gs-gate gs-gate-corner" role="dialog" aria-labelledby="gs-gate-blocked">
          <h2 id="gs-gate-blocked">Cena ainda sem escala</h2>
          <p>
            Meça duas pontas com a trena e use como referência para trabalhar em metros, centímetros
            ou polegadas reais. Sem isso, objetos e overlays ficam bloqueados.
          </p>
          <div className="gs-gate-actions">
            <button
              type="button"
              className="primary"
              onClick={() => controller?.startManualCalibration()}
            >
              Abrir trena
            </button>
            <button
              type="button"
              onClick={() => useCalibrationStore.getState().setGatePhase('hidden')}
            >
              Continuar
            </button>
          </div>
        </div>
      );
    case 'auto-confirm':
    case 'adjust':
      return (
        <AutoConfirmCard
          phase={phase}
          unit={unit}
          suggestedMeters={controller?.suggestedMeters() ?? 1}
          adjustValue={adjustValue}
          onAdjustValue={setAdjustValue}
          onConfirm={() => controller?.confirmAutoCalibration()}
          onApplyAdjust={() => {
            const parsed = Number(adjustValue.replace(',', '.'));
            if (Number.isFinite(parsed) && parsed > 0) {
              controller?.adjustAutoCalibration(toMeters(parsed, unit));
            }
          }}
          onManual={() => controller?.startManualCalibration()}
        />
      );
    default:
      return assertNever(phase);
  }
}

function AutoConfirmCard(props: {
  phase: 'auto-confirm' | 'adjust';
  unit: LengthUnit;
  suggestedMeters: number;
  adjustValue: string;
  onAdjustValue: (value: string) => void;
  onConfirm: () => void;
  onApplyAdjust: () => void;
  onManual: () => void;
}) {
  const formatted = formatMeters(props.suggestedMeters, props.unit);
  return (
    <div className="gs-gate gs-gate-corner" role="dialog" aria-labelledby="gs-gate-auto">
      <h2 id="gs-gate-auto">Confirmar auto-calibração</h2>
      <p>A distância entre estes pontos parece {formatted}?</p>
      {props.phase === 'adjust' && (
        <label className="gs-field">
          Comprimento real ({props.unit})
          <input
            type="text"
            inputMode="decimal"
            value={props.adjustValue}
            onChange={(event) => props.onAdjustValue(event.target.value)}
          />
        </label>
      )}
      <div className="gs-gate-actions">
        <button type="button" className="primary" onClick={props.onConfirm}>
          Confirmar
        </button>
        {props.phase === 'adjust' ? (
          <button type="button" onClick={props.onApplyAdjust}>
            Aplicar ajuste
          </button>
        ) : (
          <button
            type="button"
            onClick={() => useCalibrationStore.getState().setGatePhase('adjust')}
          >
            Ajustar
          </button>
        )}
        <button type="button" onClick={props.onManual}>
          Medir manualmente
        </button>
      </div>
    </div>
  );
}
