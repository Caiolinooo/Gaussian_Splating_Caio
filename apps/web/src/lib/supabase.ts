import { createClient, type Session, type SupabaseClient, type User } from '@supabase/supabase-js';

import { getLocalSession, localSessionAsSupabase } from './localAuth';

const DEV_BYPASS_FLAG = '1';
const DEV_BYPASS_TOKEN = 'dev-bypass';

function isLoopbackHostname(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
}

/**
 * Bypass só com `VITE_DEV_AUTH_BYPASS=1` **e** hostname loopback.
 * Dist bakeado com flag 1 em vm.groupabz.com não vira `dev@localhost`.
 */
export function resolveDevAuthBypass(flag: string | undefined, hostname: string | undefined): boolean {
  if (flag !== DEV_BYPASS_FLAG) {
    return false;
  }
  if (!hostname) {
    return false;
  }
  return isLoopbackHostname(hostname);
}

const DEV_BYPASS_USER = {
  id: 'dev-user',
  email: 'dev@localhost',
  app_metadata: {},
  user_metadata: {},
  aud: 'authenticated',
  created_at: '2026-01-01T00:00:00.000Z',
} as User;

const DEV_BYPASS_SESSION = {
  access_token: DEV_BYPASS_TOKEN,
  refresh_token: 'dev-bypass-refresh',
  token_type: 'bearer',
  expires_in: 3600,
  expires_at: 4_102_444_800,
  user: DEV_BYPASS_USER,
} as Session;

let client: SupabaseClient | null = null;
let clientInitError: string | null = null;

/** True quando `VITE_DEV_AUTH_BYPASS=1` **e** a UI roda em localhost. */
export function isDevAuthBypass(): boolean {
  const hostname = typeof window === 'undefined' ? undefined : window.location.hostname;
  return resolveDevAuthBypass(import.meta.env.VITE_DEV_AUTH_BYPASS, hostname);
}

export function getSupabaseUrl(): string | undefined {
  const value = import.meta.env.VITE_SUPABASE_URL;
  return value && value.length > 0 ? value : undefined;
}

export function getSupabaseAnonKey(): string | undefined {
  const value = import.meta.env.VITE_SUPABASE_ANON_KEY;
  return value && value.length > 0 ? value : undefined;
}

/**
 * Cliente Supabase (e-mail/senha + OAuth). Sessão persistida em localStorage
 * (`persistSession` + `autoRefreshToken` + `detectSessionInUrl`).
 * Retorna `null` no bypass de dev ou se as env vars ainda não foram ligadas.
 */
export function getSupabaseClient(): SupabaseClient | null {
  if (isDevAuthBypass()) {
    return null;
  }
  if (client) {
    return client;
  }
  const url = getSupabaseUrl();
  const anonKey = getSupabaseAnonKey();
  if (!url || !anonKey) {
    clientInitError =
      'Supabase não configurado. Defina VITE_SUPABASE_URL e VITE_SUPABASE_ANON_KEY (ou VITE_DEV_AUTH_BYPASS=1 em desenvolvimento).';
    return null;
  }
  client = createClient(url, anonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      storageKey: 'gs-auth',
    },
  });
  return client;
}

export function getSupabaseInitError(): string | null {
  getSupabaseClient();
  return clientInitError;
}

export async function getSession(): Promise<Session | null> {
  if (isDevAuthBypass()) {
    return DEV_BYPASS_SESSION;
  }
  const local = getLocalSession();
  if (local) {
    return localSessionAsSupabase(local);
  }
  const supabase = getSupabaseClient();
  if (!supabase) {
    return null;
  }
  const { data, error } = await supabase.auth.getSession();
  if (error) {
    return null;
  }
  return data.session;
}

export async function getCurrentUser(): Promise<User | null> {
  const session = await getSession();
  return session?.user ?? null;
}

/** Access token para `Authorization: Bearer`. No bypass devolve `dev-bypass`. */
export async function getAccessToken(): Promise<string | null> {
  if (isDevAuthBypass()) {
    return DEV_BYPASS_TOKEN;
  }
  const local = getLocalSession();
  if (local) {
    return local.access_token;
  }
  const session = await getSession();
  return session?.access_token ?? null;
}

export function subscribeAuthChanges(callback: (session: Session | null) => void): () => void {
  if (isDevAuthBypass()) {
    callback(DEV_BYPASS_SESSION);
    return () => undefined;
  }
  const supabase = getSupabaseClient();
  if (!supabase) {
    callback(null);
    return () => undefined;
  }
  const { data } = supabase.auth.onAuthStateChange((_event, session) => {
    callback(session);
  });
  return () => data.subscription.unsubscribe();
}

export { DEV_BYPASS_TOKEN, DEV_BYPASS_USER };
