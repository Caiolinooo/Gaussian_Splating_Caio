import type { ReactNode } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

import { AuthGuard } from '../features/auth';

const NAV_ITEMS = [
  { to: '/setup', label: 'Setup' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/upload', label: 'Novo upload' },
  { to: '/viewer', label: 'Viewer' },
  { to: '/editing', label: 'Edição' },
  { to: '/calibration', label: 'Calibração' },
  { to: '/overlays', label: 'Overlays' },
] as const;

export function AppNav() {
  return (
    <nav className="app-nav" aria-label="Principal">
      <span className="app-nav-brand">Gaussian Splatting</span>
      <ul className="app-nav-list">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) => (isActive ? 'app-nav-link is-active' : 'app-nav-link')}
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function AppChrome({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <AppNav />
      <div className="app-shell-main">{children}</div>
    </div>
  );
}

export function AppShell() {
  return (
    <AuthGuard>
      <AppChrome>
        <Outlet />
      </AppChrome>
    </AuthGuard>
  );
}
