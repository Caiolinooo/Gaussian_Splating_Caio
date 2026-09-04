import { createTRS } from '@gs/viewer';

import { formatMeters, fromMeters, toMeters } from '../../lib/unitsBinding';
import { isCalibrated, rootScaleFromCalibration } from '../calibration/math/scaleFactor';
import { useCalibrationStore } from '../calibration/store/calibrationStore';
import { useViewerRuntime } from '../viewer/runtime/ViewerRuntimeContext';
import { quaternionFromEulerDegrees } from './bbox/liveBounds';
import { useEditingStore } from './store/editingStore';

export function PropertiesPanel() {
  const controller = useViewerRuntime();
  const selectedId = useEditingStore((state) => state.selectedNodeId);
  const liveTrs = useEditingStore((state) => state.liveTrs);
  const liveBbox = useEditingStore((state) => state.liveBbox);
  const dragging = useEditingStore((state) => state.dragging);
  const calibration = useCalibrationStore((state) => state.calibration);
  const unit = useCalibrationStore((state) => state.unitPref.unit);
  const factor = rootScaleFromCalibration(calibration);
  const calibrated = isCalibrated(calibration);

  if (!selectedId || !liveTrs) {
    return (
      <section className="gs-panel" aria-labelledby="gs-props-title">
        <h2 id="gs-props-title">Propriedades</h2>
        <p className="muted">Selecione um objeto na cena ou no outliner.</p>
      </section>
    );
  }

  function commitPosition(axis: 'x' | 'y' | 'z', display: number): void {
    if (!controller || !liveTrs || !selectedId) {
      return;
    }
    const scene = calibrated ? displayToScene(display, unit, factor) : display;
    const position = {
      x: axis === 'x' ? scene : liveTrs.px,
      y: axis === 'y' ? scene : liveTrs.py,
      z: axis === 'z' ? scene : liveTrs.pz,
    };
    controller.applyNodeTrs(
      selectedId,
      createTRS({
        position,
        rotation: quaternionFromEulerDegrees(liveTrs.rx, liveTrs.ry, liveTrs.rz),
        scale: { x: liveTrs.sx, y: liveTrs.sy, z: liveTrs.sz },
      }),
    );
  }

  function commitRotation(axis: 'x' | 'y' | 'z', degrees: number): void {
    if (!controller || !liveTrs || !selectedId) {
      return;
    }
    const rx = axis === 'x' ? degrees : liveTrs.rx;
    const ry = axis === 'y' ? degrees : liveTrs.ry;
    const rz = axis === 'z' ? degrees : liveTrs.rz;
    controller.applyNodeTrs(
      selectedId,
      createTRS({
        position: { x: liveTrs.px, y: liveTrs.py, z: liveTrs.pz },
        rotation: quaternionFromEulerDegrees(rx, ry, rz),
        scale: { x: liveTrs.sx, y: liveTrs.sy, z: liveTrs.sz },
      }),
    );
  }

  function commitScale(axis: 'x' | 'y' | 'z', value: number): void {
    if (!controller || !liveTrs || !selectedId) {
      return;
    }
    controller.applyNodeTrs(
      selectedId,
      createTRS({
        position: { x: liveTrs.px, y: liveTrs.py, z: liveTrs.pz },
        rotation: quaternionFromEulerDegrees(liveTrs.rx, liveTrs.ry, liveTrs.rz),
        scale: {
          x: axis === 'x' ? value : liveTrs.sx,
          y: axis === 'y' ? value : liveTrs.sy,
          z: axis === 'z' ? value : liveTrs.sz,
        },
      }),
    );
  }

  const posX = calibrated ? fromMeters(liveTrs.px * factor, unit) : liveTrs.px;
  const posY = calibrated ? fromMeters(liveTrs.py * factor, unit) : liveTrs.py;
  const posZ = calibrated ? fromMeters(liveTrs.pz * factor, unit) : liveTrs.pz;

  return (
    <section className="gs-panel" aria-labelledby="gs-props-title">
      <h2 id="gs-props-title">Propriedades {dragging ? '· arraste' : ''}</h2>
      <fieldset>
        <legend>Posição ({calibrated ? unit : 'cena'})</legend>
        <AxisInput label="X" value={posX} onCommit={(value) => commitPosition('x', value)} />
        <AxisInput label="Y" value={posY} onCommit={(value) => commitPosition('y', value)} />
        <AxisInput label="Z" value={posZ} onCommit={(value) => commitPosition('z', value)} />
      </fieldset>
      <fieldset>
        <legend>Rotação (°)</legend>
        <AxisInput label="X" value={liveTrs.rx} onCommit={(value) => commitRotation('x', value)} />
        <AxisInput label="Y" value={liveTrs.ry} onCommit={(value) => commitRotation('y', value)} />
        <AxisInput label="Z" value={liveTrs.rz} onCommit={(value) => commitRotation('z', value)} />
      </fieldset>
      <fieldset>
        <legend>Escala</legend>
        <AxisInput label="X" value={liveTrs.sx} onCommit={(value) => commitScale('x', value)} />
        <AxisInput label="Y" value={liveTrs.sy} onCommit={(value) => commitScale('y', value)} />
        <AxisInput label="Z" value={liveTrs.sz} onCommit={(value) => commitScale('z', value)} />
      </fieldset>
      {liveBbox && (
        <p className="gs-bbox">
          BBox {dragging ? 'ao vivo' : ''}:{' '}
          {calibrated
            ? `${formatMeters(liveBbox.x, unit)} × ${formatMeters(liveBbox.y, unit)} × ${formatMeters(liveBbox.z, unit)}`
            : `${liveBbox.x.toFixed(3)} × ${liveBbox.y.toFixed(3)} × ${liveBbox.z.toFixed(3)} u`}
        </p>
      )}
    </section>
  );
}

function AxisInput(props: { label: string; value: number; onCommit: (value: number) => void }) {
  return (
    <label className="gs-axis">
      {props.label}
      <input
        type="text"
        inputMode="decimal"
        defaultValue={formatAxis(props.value)}
        key={formatAxis(props.value)}
        onBlur={(event) => {
          const parsed = Number(event.target.value.replace(',', '.'));
          if (Number.isFinite(parsed)) {
            props.onCommit(parsed);
          }
        }}
      />
    </label>
  );
}

function formatAxis(value: number): string {
  return value.toLocaleString('pt-BR', { maximumFractionDigits: 4 });
}

function displayToScene(
  display: number,
  unit: Parameters<typeof toMeters>[1],
  factor: number,
): number {
  const meters = toMeters(display, unit);
  return factor > 0 ? meters / factor : meters;
}
