import { useViewerRuntime } from '../runtime/ViewerRuntimeContext';
import { useViewerStore } from '../store/viewerStore';
import type { WorkspaceTool } from '../types';

const TOOLS: { id: WorkspaceTool; label: string; title?: string }[] = [
  { id: 'orbit', label: 'Órbita' },
  { id: 'fly', label: 'Voar', title: 'WASD/setas movem · Q/E sobe/desce · Shift acelera' },
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
          title={tool.title}
          onClick={() => controller?.setWorkspaceTool(tool.id)}
        >
          {tool.label}
        </button>
      ))}
    </div>
  );
}
