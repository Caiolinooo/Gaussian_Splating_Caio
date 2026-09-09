import { useState } from 'react';

import { useViewerRuntime } from '../runtime/ViewerRuntimeContext';
import { useViewerStore } from '../store/viewerStore';
import type { SplatTool } from './splatTools';

/**
 * Barra de edição de splats (C1 — corte de floaters).
 *
 * O fluxo é: escolher ferramenta de seleção → arrastar no canvas → aplicar
 * ação (excluir / ajustar / decimar). O arrasto em si é capturado pelo
 * `SplatSelectOverlay`, que desenha o retângulo/laço e chama o controller.
 */
export interface SplatEditToolbarProps {
  /** Ferramenta ativa — controlada pelo ViewerScreen (irmão do overlay). */
  tool: SplatTool;
  setTool: (tool: SplatTool) => void;
}

export function SplatEditToolbar({ tool, setTool }: SplatEditToolbarProps) {
  const controller = useViewerRuntime();
  const [target, setTarget] = useState(200000);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const gaussians = useViewerStore((state) => state.gaussianCount);
  const quality = useViewerStore((state) => state.quality);

  async function handleDecimate() {
    if (!controller) {
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const result = await controller.decimateSplats(target);
      setMessage(
        result === null
          ? 'Este backend não expõe decimação.'
          : `Decimado para ${result.toLocaleString('pt-BR')} gaussianas.`,
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Falha ao decimar.');
    } finally {
      setBusy(false);
    }
  }

  function handleDelete() {
    if (!controller) {
      return;
    }
    const removed = controller.deleteSelectedSplats();
    setMessage(
      removed === 0
        ? 'Nada selecionado — desenhe uma seleção no canvas primeiro.'
        : `${removed.toLocaleString('pt-BR')} splats removidos.`,
    );
  }

  function handleUndo() {
    if (!controller) {
      return;
    }
    setMessage(controller.undoSplatEdit() ? 'Edição desfeita.' : 'Nada a desfazer.');
  }

  return (
    <div className="gs-splat-edit" aria-label="Edição de splats">
      <div className="gs-splat-edit-tools">
        <button
          type="button"
          className={tool === 'rect' ? 'is-active' : ''}
          aria-pressed={tool === 'rect'}
          title="Seleção por retângulo — arraste no canvas"
          onClick={() => setTool(tool === 'rect' ? 'none' : 'rect')}
        >
          Retângulo
        </button>
        <button
          type="button"
          className={tool === 'lasso' ? 'is-active' : ''}
          aria-pressed={tool === 'lasso'}
          title="Seleção por laço — desenhe no canvas"
          onClick={() => setTool(tool === 'lasso' ? 'none' : 'lasso')}
        >
          Laço
        </button>
      </div>

      <div className="gs-splat-edit-actions">
        <button type="button" onClick={handleDelete} title="Remove os splats selecionados">
          Excluir seleção
        </button>
        <button
          type="button"
          onClick={() => controller?.clearSplatSelection()}
          title="Limpa a seleção atual"
        >
          Limpar
        </button>
        <button
          type="button"
          onClick={handleUndo}
          disabled={!controller?.canUndoSplatEdit}
          title="Desfaz a última edição de splat"
        >
          Desfazer
        </button>
      </div>

      <div className="gs-splat-edit-decimate">
        <label>
          Decimar até
          <input
            type="number"
            min={1000}
            step={1000}
            value={target}
            aria-label="Alvo de gaussianas"
            onChange={(event) => setTarget(Number(event.target.value))}
          />
        </label>
        <button type="button" onClick={handleDecimate} disabled={busy}>
          {busy ? 'Decimando…' : 'Decimar'}
        </button>
      </div>

      <p className="gs-splat-edit-hint">
        {gaussians.toLocaleString('pt-BR')} gaussianas · SH {quality.shDegree}
        {tool !== 'none' && ' · arraste no canvas para selecionar'}
      </p>
      {message && <p className="gs-splat-edit-message">{message}</p>}
    </div>
  );
}
