import { ViewerRoute } from '../viewer/ViewerRoute';
import type { ViewerRouteProps } from '../viewer/types';

/** Abre o workspace com a trena ativa. */
export function CalibrationRoute(props: ViewerRouteProps = {}) {
  return <ViewerRoute {...props} initialTool={props.initialTool ?? 'tape'} />;
}
