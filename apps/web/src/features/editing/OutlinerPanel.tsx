import type { OutlinerKind } from '@gs/viewer';
import { useState } from 'react';

import { isCalibrated } from '../calibration/math/scaleFactor';
import { assertNever } from '../viewer/assertNever';
import { useCalibrationStore } from '../calibration/store/calibrationStore';
import { useViewerRuntime } from '../viewer/runtime/ViewerRuntimeContext';
import { useEditingStore } from './store/editingStore';

export function OutlinerPanel() {
  const controller = useViewerRuntime();
  const items = useEditingStore((state) => state.items);
  const selectedId = useEditingStore((state) => state.selectedNodeId);
  const calibrated = useCalibrationStore((state) => isCalibrated(state.calibration));
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  return (
    <section className="gs-panel" aria-labelledby="gs-outliner-title">
      <header className="gs-panel-head">
        <h2 id="gs-outliner-title">Outliner</h2>
      </header>
      {items.length === 0 ? (
        <p className="muted">Nenhum objeto na cena.</p>
      ) : (
        <ul className="gs-outliner">
          {items.map((item) => (
            <li
              key={item.id}
              className={item.id === selectedId ? 'is-selected' : undefined}
              style={{ paddingLeft: `${0.5 + item.depth * 0.75}rem` }}
            >
              <button
                type="button"
                className="gs-outliner-name"
                onClick={() => controller?.selectNode(item.id)}
              >
                {kindGlyph(item.kind)} {item.name}
              </button>
              <button
                type="button"
                onClick={() => controller?.setNodeVisible(item.id, !item.visible)}
                aria-label={item.visible ? 'Ocultar' : 'Mostrar'}
              >
                {item.visible ? '◉' : '○'}
              </button>
              {!item.locked && (
                <>
                  <button
                    type="button"
                    disabled={!calibrated}
                    onClick={() => controller?.duplicateNode(item.id)}
                    aria-label="Duplicar"
                  >
                    Dup
                  </button>
                  <button
                    type="button"
                    onClick={() => controller?.deleteNode(item.id)}
                    aria-label="Excluir"
                  >
                    Del
                  </button>
                </>
              )}
              <button
                type="button"
                onClick={() => {
                  setRenameId(item.id);
                  setRenameValue(item.name);
                }}
                aria-label="Renomear"
              >
                ✎
              </button>
            </li>
          ))}
        </ul>
      )}
      {renameId && (
        <form
          className="gs-rename"
          onSubmit={(event) => {
            event.preventDefault();
            if (renameValue.trim()) {
              controller?.renameNode(renameId, renameValue.trim());
            }
            setRenameId(null);
          }}
        >
          <input
            value={renameValue}
            onChange={(event) => setRenameValue(event.target.value)}
            aria-label="Novo nome"
            autoFocus
          />
          <button type="submit" className="primary">
            OK
          </button>
        </form>
      )}
    </section>
  );
}

function kindGlyph(kind: OutlinerKind): string {
  switch (kind) {
    case 'background-splat':
      return '◈';
    case 'glb':
      return '▢';
    case 'splat':
      return '◌';
    default:
      return assertNever(kind);
  }
}
