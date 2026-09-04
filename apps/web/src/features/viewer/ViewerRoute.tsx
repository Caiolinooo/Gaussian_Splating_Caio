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
import type { ViewerRouteProps } from './types';
import { ViewerScreen } from './ViewerScreen';

/** Rota do workspace 3D (viewer + edição + trena + overlays). A consolidação liga o router. */
export function ViewerRoute(props: ViewerRouteProps = {}) {
  return (
    <ViewerScreen {...props}>
      <div className="gs-chrome gs-chrome-top">
        <SceneFileBar />
        <GizmoToolbar />
        <UnitSelector />
        <CameraPresetsBar />
      </div>
      <aside className="gs-chrome gs-chrome-left">
        <OutlinerPanel />
        <TrenaTool />
      </aside>
      <aside className="gs-chrome gs-chrome-right">
        <PropertiesPanel />
        <OverlayEditor />
      </aside>
      <div className="gs-chrome gs-chrome-bottom">
        <ViewerHud />
      </div>
      <LoadProgress />
      <CalibrationGate />
    </ViewerScreen>
  );
}
