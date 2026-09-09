import { useViewerRuntime } from '../runtime/ViewerRuntimeContext';
import { useViewerStore } from '../store/viewerStore';
import type { WorkspaceTool } from '../types';

const TOOLS: { id: WorkspaceTool; label: string }[] = [
  { id: 'orbit', label: 'Órbita' },
  { id: 'tape', label: 'Trena' },
  { id: 'edit', label: 'Edição' },
  { id: 'overlay', label: 'Overlays' },
];

export function WorkspaceToolBar() {
  const controller = useViewerRuntime();
  const active = useViewerStore((state) => state.workspaceTool);

  return (
    <div className="gs-tools" role="tablist" aria-label="Ferramentas do viewer">
      {TOOLS.map((tool) => (
        <button
          key={tool.id}
          type="button"
          role="tab"
          aria-selected={tool.id === active}
          className={tool.id === active ? 'primary' : undefined}
          onClick={() => controller?.setWorkspaceTool(tool.id)}
        >
          {tool.label}
        </button>
      ))}
    </div>
  );
}
