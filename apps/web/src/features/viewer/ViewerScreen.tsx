import { useEffect, useRef, useState, type ReactNode } from 'react';

import { resolveViewerParams } from './hooks/useViewerParams';
import { ViewerController } from './runtime/ViewerController';
import { ViewerRuntimeProvider } from './runtime/ViewerRuntimeContext';
import type { ViewerRouteProps } from './types';
import './viewer.css';

interface ViewerScreenProps extends ViewerRouteProps {
  children?: ReactNode;
}

export function ViewerScreen({ children, ...props }: ViewerScreenProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [controller, setController] = useState<ViewerController | null>(null);
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

  return (
    <ViewerRuntimeProvider value={controller}>
      <div className="gs-workspace">
        <canvas ref={canvasRef} className="gs-canvas" tabIndex={0} aria-label="Viewport 3D" />
        {children}
      </div>
    </ViewerRuntimeProvider>
  );
}
