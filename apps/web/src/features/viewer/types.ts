import type { BackendDetection, RendererBackendKind, SplatQuality } from '@gs/viewer';

export type WorkspaceTool = 'orbit' | 'tape' | 'edit' | 'overlay';

export type CameraPreset = 'front' | 'side' | 'top' | 'iso';

export interface ViewerRouteProps {
  jobId?: string;
  sceneId?: string;
  initialTool?: WorkspaceTool;
}

export interface ViewerHudSnapshot {
  fps: number;
  gaussianCount: number;
  backend: BackendDetection | null;
  quality: SplatQuality;
  memoryMb: number | null;
}

export interface ResolvedViewerParams {
  jobId?: string;
  sceneId?: string;
  initialTool: WorkspaceTool;
  forceBackend?: RendererBackendKind;
}

export function isCameraPreset(value: string): value is CameraPreset {
  switch (value) {
    case 'front':
    case 'side':
    case 'top':
    case 'iso':
      return true;
    default:
      return false;
  }
}

export function isWorkspaceTool(value: string): value is WorkspaceTool {
  switch (value) {
    case 'orbit':
    case 'tape':
    case 'edit':
    case 'overlay':
      return true;
    default:
      return false;
  }
}
