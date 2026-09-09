import { createContext, useContext } from 'react';

import type { SplatTool } from '../components/splatTools';

/**
 * Ponte entre a barra de edição de splats e o overlay que captura o arrasto.
 * Os dois são irmãos na árvore, então o estado vive no `ViewerScreen` e chega
 * aqui por contexto.
 */
export interface SplatSelectionBridge {
  tool: SplatTool;
  setTool: (tool: SplatTool) => void;
}

const DEFAULT_BRIDGE: SplatSelectionBridge = {
  tool: 'none',
  setTool: () => {},
};

export const SplatSelectionContext = createContext<SplatSelectionBridge>(DEFAULT_BRIDGE);

export function useSplatSelection(): SplatSelectionBridge {
  return useContext(SplatSelectionContext);
}
