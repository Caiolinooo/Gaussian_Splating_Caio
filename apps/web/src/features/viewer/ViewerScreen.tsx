import { useEffect, useRef, useState, type ReactNode } from 'react';

import { resolveViewerParams } from './hooks/useViewerParams';
import { ViewerController } from './runtime/ViewerController';
import { ViewerRuntimeProvider } from './runtime/ViewerRuntimeContext';
import type { ViewerRouteProps } from './types';
import './viewer.css';
import { SplatSelectOverlay, type SplatSelectOverlayProps } from './components/SplatSelectOverlay';
import type { SplatTool } from './components/splatTools';
import { SplatSelectionContext, type SplatSelectionBridge } from './runtime/SplatSelectionContext';

interface ViewerScreenProps extends ViewerRouteProps {
  children?: ReactNode;
}

/**
 * Estado da ferramenta de seleção de splats vive aqui (não na toolbar) porque
 * o overlay que captura o arrasto e a toolbar são irmãos na árvore — os dois
 * leem a mesma ferramenta ativa via `SplatSelectionContext`.
 */
export function ViewerScreen({ children, ...props }: ViewerScreenProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [controller, setController] = useState<ViewerController | null>(null);
  const [splatTool, setSplatTool] = useState<SplatTool>('none');
  const params = resolveViewerParams(props);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const next = new ViewerController(canvas);
    setController(next);
    void next.boot({
      jobId: params.jobId,
      sceneId: params.sceneId,
      forceBackend: params.forceBackend,
      initialTool: params.initialTool,
    });
    return () => {
      next.dispose();
      setController(null);
    };
  }, [params.jobId, params.sceneId, params.forceBackend, params.initialTool]);

  // Desliga a seleção quando a cena é trocada (índices não valem mais).
  useEffect(() => {
    setSplatTool('none');
  }, [params.jobId, params.sceneId]);

  const handleSelectRect: SplatSelectOverlayProps['onSelectRect'] = (rect) => {
    controller?.selectSplatsByRect(rect, 'replace');
  };

  const handleSelectLasso: SplatSelectOverlayProps['onSelectLasso'] = (points) => {
    controller?.selectSplatsByLasso(points, 'replace');
  };

  const bridge: SplatSelectionBridge = { tool: splatTool, setTool: setSplatTool };

  return (
    <ViewerRuntimeProvider value={controller}>
      <SplatSelectionContext.Provider value={bridge}>
        <div className="gs-workspace">
          <canvas ref={canvasRef} className="gs-canvas" tabIndex={0} aria-label="Viewport 3D" />
          <SplatSelectOverlay
            tool={splatTool}
            onSelectRect={handleSelectRect}
            onSelectLasso={handleSelectLasso}
            onDeactivate={() => setSplatTool('none')}
          />
          {children}
        </div>
      </SplatSelectionContext.Provider>
    </ViewerRuntimeProvider>
  );
}
