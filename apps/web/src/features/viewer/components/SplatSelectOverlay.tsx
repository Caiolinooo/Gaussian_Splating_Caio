import { useEffect, useRef, useState } from 'react';

import type { SplatTool } from './splatTools';

/**
 * Captura o arrasto de seleção sobre o canvas (retângulo ou laço).
 *
 * Fica por cima do canvas sem roubar os eventos de órbita: só intercepta
 * quando uma ferramenta de seleção está ativa. O resultado é desenhado aqui
 * (SVG) e aplicado no controller ao soltar o ponteiro.
 */
export interface SplatSelectOverlayProps {
  tool: SplatTool;
  onSelectRect: (rect: { x: number; y: number; width: number; height: number }) => void;
  onSelectLasso: (points: { x: number; y: number }[]) => void;
  onDeactivate: () => void;
}

const LASSO_MIN_POINTS = 3;
const LASSO_SAMPLE_PX = 6;

export function SplatSelectOverlay({
  tool,
  onSelectRect,
  onSelectLasso,
  onDeactivate,
}: SplatSelectOverlayProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [drag, setDrag] = useState<{
    startX: number;
    startY: number;
    x: number;
    y: number;
  } | null>(null);
  const [lasso, setLasso] = useState<{ x: number; y: number }[]>([]);

  // Esc cancela a ferramenta; limpa estado ao trocar de ferramenta.
  useEffect(() => {
    setDrag(null);
    setLasso([]);
  }, [tool]);

  useEffect(() => {
    if (tool === 'none') {
      return;
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setDrag(null);
        setLasso([]);
        onDeactivate();
      }
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [tool, onDeactivate]);

  if (tool === 'none') {
    return null;
  }

  function localPoint(event: React.PointerEvent): { x: number; y: number } {
    const rect = hostRef.current?.getBoundingClientRect();
    return {
      x: event.clientX - (rect?.left ?? 0),
      y: event.clientY - (rect?.top ?? 0),
    };
  }

  function handlePointerDown(event: React.PointerEvent) {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    (event.target as Element).setPointerCapture?.(event.pointerId);
    const point = localPoint(event);
    if (tool === 'rect') {
      setDrag({ startX: point.x, startY: point.y, x: point.x, y: point.y });
    } else {
      setLasso([point]);
    }
  }

  function handlePointerMove(event: React.PointerEvent) {
    const point = localPoint(event);
    if (tool === 'rect' && drag) {
      setDrag({ ...drag, x: point.x, y: point.y });
    } else if (tool === 'lasso' && lasso.length > 0) {
      const last = lasso[lasso.length - 1];
      if (!last) {
        return;
      }
      // Amostragem por distância: evita polígonos com milhares de pontos.
      const dx = point.x - last.x;
      const dy = point.y - last.y;
      if (Math.hypot(dx, dy) >= LASSO_SAMPLE_PX) {
        setLasso([...lasso, point]);
      }
    }
  }

  function handlePointerUp(event: React.PointerEvent) {
    event.stopPropagation();
    if (tool === 'rect' && drag) {
      const rect = normalizeRect(drag.startX, drag.startY, drag.x, drag.y);
      setDrag(null);
      // Ignora cliques sem arrasto (foi só um toque).
      if (rect.width > 4 && rect.height > 4) {
        onSelectRect(rect);
      }
    } else if (tool === 'lasso') {
      const points = lasso;
      setLasso([]);
      if (points.length >= LASSO_MIN_POINTS) {
        onSelectLasso(points);
      }
    }
  }

  const rectStyle = drag ? normalizeRect(drag.startX, drag.startY, drag.x, drag.y) : null;

  return (
    <div
      ref={hostRef}
      className="gs-splat-select"
      style={{ position: 'absolute', inset: 0, cursor: 'crosshair', touchAction: 'none' }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0 }}>
        {tool === 'rect' && rectStyle && (
          <rect
            x={rectStyle.x}
            y={rectStyle.y}
            width={rectStyle.width}
            height={rectStyle.height}
            fill="rgba(34, 197, 94, 0.12)"
            stroke="#22c55e"
            strokeWidth={1}
            strokeDasharray="4 3"
          />
        )}
        {tool === 'lasso' && lasso.length > 1 && (
          <polyline
            points={lasso.map((p) => `${p.x},${p.y}`).join(' ')}
            fill="rgba(34, 197, 94, 0.12)"
            stroke="#22c55e"
            strokeWidth={1}
            strokeDasharray="4 3"
          />
        )}
      </svg>
    </div>
  );
}

function normalizeRect(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): { x: number; y: number; width: number; height: number } {
  return {
    x: Math.min(x1, x2),
    y: Math.min(y1, y2),
    width: Math.abs(x2 - x1),
    height: Math.abs(y2 - y1),
  };
}
