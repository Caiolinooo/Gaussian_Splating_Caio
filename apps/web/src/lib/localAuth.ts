import type { Session, User } from '@supabase/supabase-js';

import { getApiBaseUrl } from './api';
import { LOCAL_AUTH_STORAGE_KEY } from './sessionInvalidation';

/**
 * Login local (sem Supabase): a API emite JWT HS256 quando
 * `LOCAL_AUTH_USER`/`LOCAL_AUTH_PASSWORD` estão configurados no servidor.
 * Sessão persistida em localStorage (`gs-local-auth`).
 */

const STORAGE_KEY = LOCAL_AUTH_STORAGE_KEY;

export interface LocalSession {
  access_token: string;
  expires_at: number;
  user: { id: string; email: string | null };
}

export interface LocalAuthInfo {
  enabled: boolean;
  username: string | null;
}

function storage(): Storage | null {
  return typeof localStorage === 'undefined' ? null : localStorage;
}

export function getLocalSession(): LocalSession | null {
  const store = storage();
  if (!store) {
    return null;
  }
  try {
    const raw = store.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<LocalSession>;
    if (typeof parsed.access_token !== 'string' || typeof parsed.expires_at !== 'number') {
      return null;
    }
    const jwtParts = parsed.access_token.split('.');
    if (parsed.access_token === 'dev-bypass' || jwtParts.length !== 3 || jwtParts.some((part) => !part)) {
      store.removeItem(STORAGE_KEY);
      return null;
    }
    if (!parsed.user || typeof parsed.user.id !== 'string') {
      return null;
    }
    if (parsed.expires_at * 1000 <= Date.now()) {
      store.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed as LocalSession;
  } catch {
    return null;
  }
}

export function clearLocalSession(): void {
  storage()?.removeItem(STORAGE_KEY);
}

/** Sessão local no formato Supabase — mesmo padrão do bypass de dev. */
export function localSessionAsSupabase(session: LocalSession): Session {
  const user = {
    id: session.user.id,
    email: session.user.email ?? undefined,
    app_metadata: {},
    user_metadata: {},
    aud: 'authenticated',
    created_at: new Date().toISOString(),
  } as User;
  return {
    access_token: session.access_token,
    refresh_token: '',
    token_type: 'bearer',
    expires_in: Math.max(0, session.expires_at - Math.floor(Date.now() / 1000)),
    expires_at: session.expires_at,
    user,
  } as Session;
}

export async function fetchLocalAuthInfo(signal?: AbortSignal): Promise<LocalAuthInfo> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/auth/local`, {
      headers: { Accept: 'application/json' },
      signal,
    });
    if (!response.ok) {
      return { enabled: false, username: null };
    }
    const body = (await response.json()) as Partial<LocalAuthInfo>;
    return {
      enabled: body.enabled === true,
      username: typeof body.username === 'string' ? body.username : null,
    };
  } catch {
    return { enabled: false, username: null };
  }
}

export type LocalSignInResult = { ok: true } | { ok: false; error: string };

export async function signInLocal(username: string, password: string): Promise<LocalSignInResult> {
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ username: username.trim(), password }),
    });
  } catch {
    return { ok: false, error: 'Não foi possível conectar à API para entrar.' };
  }
  if (!response.ok) {
    let message = `Erro ${response.status} ao entrar.`;
    try {
      const body = (await response.json()) as { detail?: { message?: string } | string };
      if (typeof body.detail === 'string' && body.detail.trim()) {
        message = body.detail;
      } else if (body.detail && typeof body.detail === 'object' && body.detail.message) {
        message = body.detail.message;
      }
    } catch {
      // mantém a mensagem genérica
    }
    return { ok: false, error: message };
  }
  const body = (await response.json()) as {
    access_token?: string;
    expires_in?: number;
    user?: { id?: string; email?: string | null };
  };
  if (!body.access_token || !body.user?.id) {
    return { ok: false, error: 'A API devolveu uma sessão inválida.' };
  }
  const session: LocalSession = {
    access_token: body.access_token,
    expires_at: Math.floor(Date.now() / 1000) + (body.expires_in ?? 7 * 24 * 3600),
    user: { id: body.user.id, email: body.user.email ?? null },
  };
  storage()?.setItem(STORAGE_KEY, JSON.stringify(session));
  return { ok: true };
}
