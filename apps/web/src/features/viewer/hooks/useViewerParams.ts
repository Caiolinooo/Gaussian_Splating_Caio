import type { RendererBackendKind } from '@gs/viewer';

import { isWorkspaceTool, type ResolvedViewerParams, type ViewerRouteProps } from '../types';

export function resolveViewerParams(props: ViewerRouteProps = {}): ResolvedViewerParams {
  const search = new URLSearchParams(window.location.search);
  const jobId = props.jobId ?? search.get('job') ?? search.get('jobId') ?? undefined;
  const sceneId = props.sceneId ?? search.get('sceneId') ?? undefined;
  const toolRaw = search.get('tool') ?? props.initialTool ?? 'orbit';
  const backendRaw = search.get('backend');
  return {
    jobId: emptyToUndef(jobId),
    sceneId: emptyToUndef(sceneId),
    initialTool: isWorkspaceTool(toolRaw) ? toolRaw : 'orbit',
    forceBackend: parseBackend(backendRaw),
  };
}

function emptyToUndef(value: string | undefined): string | undefined {
  return value && value.length > 0 ? value : undefined;
}

function parseBackend(value: string | null): RendererBackendKind | undefined {
  switch (value) {
    case 'spark':
    case 'mkkellogg':
      return value;
    default:
      return undefined;
  }
}
