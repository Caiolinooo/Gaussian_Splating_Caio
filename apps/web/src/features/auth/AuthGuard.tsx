import { useEffect, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { isDevAuthBypass } from '../../lib/supabase';
import { AUTH_PATHS, isAuthenticated, useAuthStore } from './authStore';

export interface AuthGuardProps {
  children: ReactNode;
  fallback?: ReactNode;
  redirectHref?: string;
  onUnauthenticated?: () => void;
}

/**
 * Sem sessão (e sem bypass de dev) redireciona para `/login`.
 */
export function AuthGuard({
  children,
  fallback,
  redirectHref = AUTH_PATHS.login,
  onUnauthenticated,
}: AuthGuardProps) {
  const ready = useAuthStore((state) => state.ready);
  const session = useAuthStore((state) => state.session);
  const user = useAuthStore((state) => state.user);
  const initialize = useAuthStore((state) => state.initialize);
  const allowed = isDevAuthBypass() || isAuthenticated({ session, user });
  const location = useLocation();

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (!ready || allowed) {
      return;
    }
    onUnauthenticated?.();
  }, [ready, allowed, onUnauthenticated]);

  if (!ready) {
    return (
      <main className="auth-screen">
        <p className="muted">Carregando sessão…</p>
      </main>
    );
  }

  if (!allowed) {
    if (fallback) {
      return (
        <>
          {fallback}
          <span hidden data-auth-redirect={redirectHref} />
        </>
      );
    }
    return <Navigate to={redirectHref} replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}
