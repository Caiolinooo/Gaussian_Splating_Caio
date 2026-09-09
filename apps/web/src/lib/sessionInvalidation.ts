/**
 * Sessão morta no cliente: 401 da API, token inválido ou `dev-bypass` recusado.
 * Não importa api/localAuth/authStore — evita ciclo de import.
 */

export const LOCAL_AUTH_STORAGE_KEY = 'gs-local-auth';
export const SUPABASE_AUTH_STORAGE_KEY = 'gs-auth';
export const LOGIN_PATH = '/login';

const SESSION_FAILURE_CODES = new Set([
  'UNAUTHENTICATED',
  'TOKEN_INVALID',
  'TOKEN_EXPIRED',
  'UNSUPPORTED_ALG',
]);

export interface AuthFailureLike {
  status?: number;
  errorCode?: string;
  message?: string;
}

export function isAuthFailure(error: AuthFailureLike): boolean {
  if (error.status !== 401) {
    return false;
  }
  if (error.errorCode === 'INVALID_CREDENTIALS') {
    return false;
  }
  if (!error.errorCode) {
    return true;
  }
  return SESSION_FAILURE_CODES.has(error.errorCode);
}

export function clearClientAuthStorage(): void {
  if (typeof localStorage === 'undefined') {
    return;
  }
  localStorage.removeItem(LOCAL_AUTH_STORAGE_KEY);
  localStorage.removeItem(SUPABASE_AUTH_STORAGE_KEY);
}

/** Limpa `gs-local-auth` / `gs-auth` e manda para `/login` (exceto se já estiver lá). */
export function invalidateClientSession(): void {
  clearClientAuthStorage();
  if (typeof window === 'undefined') {
    return;
  }
  const path = window.location.pathname;
  if (path === LOGIN_PATH || path.startsWith(`${LOGIN_PATH}/`)) {
    return;
  }
  window.location.replace(LOGIN_PATH);
}
