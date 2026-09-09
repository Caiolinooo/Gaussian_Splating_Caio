import { CalibrationGate } from '../calibration/CalibrationGate';
import { TrenaTool } from '../calibration/TrenaTool';
import { UnitSelector } from '../calibration/UnitSelector';
import '../calibration/calibration.css';
import { GizmoToolbar } from '../editing/GizmoToolbar';
import { OutlinerPanel } from '../editing/OutlinerPanel';
import { PropertiesPanel } from '../editing/PropertiesPanel';
import { SceneFileBar } from '../editing/SceneFileBar';
import '../editing/editing.css';
import { OverlayEditor } from '../overlays/OverlayEditor';
import '../overlays/overlays.css';
import { CameraPresetsBar } from './components/CameraPresetsBar';
import { LoadProgress } from './components/LoadProgress';
import { ViewerHud } from './components/ViewerHud';
import { WorkspaceToolBar } from './components/WorkspaceToolBar';
import { useViewerStore } from './store/viewerStore';
import type { ViewerRouteProps } from './types';
import { ViewerScreen } from './ViewerScreen';

/** Workspace 3D: uma nav de app + ferramentas no viewer (sem abas duplicadas). */
export function ViewerRoute(props: ViewerRouteProps = {}) {
  return (
    <ViewerScreen {...props}>
      <ViewerChrome />
      <LoadProgress />
      <CalibrationGate />
    </ViewerScreen>
  );
}

function ViewerChrome() {
  const tool = useViewerStore((state) => state.workspaceTool);
  const showEdit = tool === 'edit';
  const showTape = tool === 'tape';
  const showOverlay = tool === 'overlay';

  return (
    <>
      <div className="gs-chrome gs-chrome-top">
        <WorkspaceToolBar />
        <SceneFileBar />
        {showEdit ? <GizmoToolbar /> : null}
        {showTape || showEdit ? <UnitSelector /> : null}
        <CameraPresetsBar />
      </div>
      {showEdit || showTape ? (
        <aside className="gs-chrome gs-chrome-left">
          {showEdit ? <OutlinerPanel /> : null}
          {showTape ? <TrenaTool /> : null}
        </aside>
      ) : null}
      {showEdit || showOverlay ? (
        <aside className="gs-chrome gs-chrome-right">
          {showEdit ? <PropertiesPanel /> : null}
          {showOverlay ? <OverlayEditor /> : null}
        </aside>
      ) : null}
      <div className="gs-chrome gs-chrome-bottom">
        <ViewerHud />
      </div>
    </>
  );
}
