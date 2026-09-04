import { createContext, useContext } from 'react';

import type { ViewerController } from './ViewerController';

const ViewerRuntimeContext = createContext<ViewerController | null>(null);

export const ViewerRuntimeProvider = ViewerRuntimeContext.Provider;

export function useViewerRuntime(): ViewerController | null {
  return useContext(ViewerRuntimeContext);
}

export function useViewerRuntimeRequired(): ViewerController {
  const controller = useContext(ViewerRuntimeContext);
  if (!controller) {
    throw new Error('ViewerRuntime indisponível — monte o painel dentro de ViewerRoute.');
  }
  return controller;
}
