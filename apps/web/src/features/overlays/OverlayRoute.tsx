import { ViewerRoute } from '../viewer/ViewerRoute';
import type { ViewerRouteProps } from '../viewer/types';

/** Abre o workspace pronto para aplicar overlay. */
export function OverlayRoute(props: ViewerRouteProps = {}) {
  return <ViewerRoute {...props} initialTool={props.initialTool ?? 'overlay'} />;
}
