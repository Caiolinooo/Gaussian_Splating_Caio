import { ViewerRoute } from '../viewer/ViewerRoute';
import type { ViewerRouteProps } from '../viewer/types';

/** Mesmo workspace do viewer — a consolidação pode apontar /edit para cá. */
export function EditingRoute(props: ViewerRouteProps = {}) {
  return <ViewerRoute {...props} />;
}
