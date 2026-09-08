import type { BlendMode, LengthUnit, OverlayKind } from '@gs/overlays';

import { formatInUnit, fromMeters, toMeters } from '../../lib/unitsBinding';
import { isCalibrated } from '../calibration/math/scaleFactor';
import { useCalibrationStore } from '../calibration/store/calibrationStore';
import { useViewerRuntime } from '../viewer/runtime/ViewerRuntimeContext';
import { OverlayList } from './OverlayList';
import { blendModeLabelPt, overlayKindLabelPt } from './overlayPersist';
import { useOverlayStore } from './store/overlayStore';

const KINDS: OverlayKind[] = ['paint', 'wallpaper', 'sticker'];
const BLENDS: BlendMode[] = ['normal', 'multiply', 'overlay'];
const SIZE_UNITS: LengthUnit[] = ['mm', 'cm', 'm', 'in', 'ft'];

export function OverlayEditor() {
  const controller = useViewerRuntime();
  const draft = useOverlayStore((state) => state.draft);
  const error = useOverlayStore((state) => state.error);
  const calibrated = useCalibrationStore((state) => isCalibrated(state.calibration));
  const patch = useOverlayStore((state) => state.patchDraft);

  function onImage(file: File | undefined): void {
    if (!file) {
      return;
    }
    if (draft.imageUrl) {
      URL.revokeObjectURL(draft.imageUrl);
    }
    patch({ imageUrl: URL.createObjectURL(file), imageName: file.name });
  }

  function onUnitChange(next: LengthUnit): void {
    const widthM = toMeters(draft.width, draft.sizeUnit);
    const heightM = toMeters(draft.height, draft.sizeUnit);
    patch({
      sizeUnit: next,
      width: fromMeters(widthM, next),
      height: fromMeters(heightM, next),
    });
    queueMicrotask(() => controller?.previewSelectedOverlay());
  }

  return (
    <section className="gs-panel" aria-labelledby="gs-overlay-title">
      <header className="gs-panel-head">
        <h2 id="gs-overlay-title">Overlays</h2>
      </header>
      {!calibrated && (
        <p className="gs-warn">Calibre a cena para aplicar pintura, papel de parede ou adesivos.</p>
      )}
      <label className="gs-field">
        Tipo
        <select
          value={draft.kind}
          onChange={(event) => patch({ kind: event.target.value as OverlayKind })}
        >
          {KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {overlayKindLabelPt(kind)}
            </option>
          ))}
        </select>
      </label>
      <label className="gs-field">
        Imagem
        <input
          type="file"
          accept="image/*"
          onChange={(event) => onImage(event.target.files?.[0])}
        />
        {draft.imageName && <span className="muted">{draft.imageName}</span>}
      </label>
      {draft.kind === 'paint' && (
        <label className="gs-field">
          Cor
          <input
            type="color"
            value={draft.color}
            onChange={(event) => patch({ color: event.target.value })}
          />
        </label>
      )}
      <div className="gs-size-row">
        <label className="gs-field">
          Largura
          <input
            type="text"
            inputMode="decimal"
            value={String(draft.width).replace('.', ',')}
            onChange={(event) => {
              const parsed = Number(event.target.value.replace(',', '.'));
              if (Number.isFinite(parsed) && parsed > 0) {
                patch({ width: parsed });
                queueMicrotask(() => controller?.previewSelectedOverlay());
              }
            }}
          />
        </label>
        <label className="gs-field">
          Altura
          <input
            type="text"
            inputMode="decimal"
            value={String(draft.height).replace('.', ',')}
            onChange={(event) => {
              const parsed = Number(event.target.value.replace(',', '.'));
              if (Number.isFinite(parsed) && parsed > 0) {
                patch({ height: parsed });
                queueMicrotask(() => controller?.previewSelectedOverlay());
              }
            }}
          />
        </label>
        <label className="gs-field">
          Unidade
          <select
            value={draft.sizeUnit}
            onChange={(event) => onUnitChange(event.target.value as LengthUnit)}
          >
            {SIZE_UNITS.map((unit) => (
              <option key={unit} value={unit}>
                {unit}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted">
        {draft.kind === 'sticker'
          ? `Adesivo ${formatInUnit(draft.width, draft.sizeUnit)} × ${formatInUnit(draft.height, draft.sizeUnit)}`
          : draft.kind === 'wallpaper'
            ? `Estampa ${formatInUnit(draft.width, draft.sizeUnit)} × ${formatInUnit(draft.height, draft.sizeUnit)}`
            : `Região ${formatInUnit(draft.width, draft.sizeUnit)} × ${formatInUnit(draft.height, draft.sizeUnit)}`}
      </p>
      <label className="gs-field">
        Opacidade
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={draft.opacity}
          onChange={(event) => {
            patch({ opacity: Number(event.target.value) });
            queueMicrotask(() => controller?.previewSelectedOverlay());
          }}
        />
      </label>
      <label className="gs-field">
        Mistura
        <select
          value={draft.blendMode}
          onChange={(event) => {
            patch({ blendMode: event.target.value as BlendMode });
            queueMicrotask(() => controller?.previewSelectedOverlay());
          }}
        >
          {BLENDS.map((mode) => (
            <option key={mode} value={mode}>
              {blendModeLabelPt(mode)}
            </option>
          ))}
        </select>
      </label>
      <label className="gs-check">
        <input
          type="checkbox"
          checked={draft.maskEnabled}
          onChange={(event) => patch({ maskEnabled: event.target.checked })}
        />
        Máscara por normal (anti-sangramento)
      </label>
      <button
        type="button"
        className="primary"
        disabled={!calibrated || (draft.kind !== 'paint' && !draft.imageUrl)}
        onClick={() => patch({ placementMode: !draft.placementMode })}
      >
        {draft.placementMode ? 'Clique na superfície…' : 'Aplicar na cena'}
      </button>
      {error && <p className="gs-warn">{error}</p>}
      <OverlayList />
    </section>
  );
}
