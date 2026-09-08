import { create } from 'zustand';
import type { Session, User } from '@supabase/supabase-js';

import {
  clearLocalSession,
  fetchLocalAuthInfo,
  getLocalSession,
  localSessionAsSupabase,
  signInLocal,
} from '../../lib/localAuth';
import {
  getSupabaseClient,
  getSupabaseInitError,
  isDevAuthBypass,
  subscribeAuthChanges,
  DEV_BYPASS_USER,
} from '../../lib/supabase';
import { isValidEmail, mapAuthError } from './authErrors';

export const AUTH_PATHS = {
  login: '/login',
  signup: '/signup',
  reset: '/reset',
} as const;

export type AuthPage = keyof typeof AUTH_PATHS;

interface AuthStore {
  ready: boolean;
  session: Session | null;
  user: User | null;
  loading: boolean;
  error: string | null;
  info: string | null;
  /** Login local (sem Supabase) habilitado no servidor; `defaultUsername` pré-preenche o campo. */
  localAuthEnabled: boolean;
  defaultUsername: string | null;
  initialize: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<boolean>;
  signUp: (email: string, password: string) => Promise<boolean>;
  signInWithGoogle: () => Promise<boolean>;
  resetPassword: (email: string) => Promise<boolean>;
  signOut: () => Promise<void>;
  clearMessages: () => void;
}

let initialized = false;
let stopListening: (() => void) | null = null;

function applySession(session: Session | null): Pick<AuthStore, 'session' | 'user'> {
  return { session, user: session?.user ?? (isDevAuthBypass() ? DEV_BYPASS_USER : null) };
}

export const useAuthStore = create<AuthStore>((set) => ({
  ready: false,
  session: null,
  user: isDevAuthBypass() ? DEV_BYPASS_USER : null,
  loading: false,
  error: null,
  info: null,
  localAuthEnabled: false,
  defaultUsername: null,

  initialize: async () => {
    if (initialized) {
      set({ ready: true });
      return;
    }
    initialized = true;
    if (isDevAuthBypass()) {
      set({ ready: true, user: DEV_BYPASS_USER, session: null, error: null });
      return;
    }
    const client = getSupabaseClient();
    if (!client) {
      const localInfo = await fetchLocalAuthInfo();
      const local = getLocalSession();
      if (local) {
        const session = localSessionAsSupabase(local);
        set({
          ready: true,
          session,
          user: session.user,
          error: null,
          localAuthEnabled: localInfo.enabled,
          defaultUsername: localInfo.username,
        });
        return;
      }
      set({
        ready: true,
        error: localInfo.enabled ? null : getSupabaseInitError(),
        localAuthEnabled: localInfo.enabled,
        defaultUsername: localInfo.username,
      });
      return;
    }
    const { data } = await client.auth.getSession();
    set({ ready: true, ...applySession(data.session), error: null });
    stopListening = subscribeAuthChanges((session) => {
      set(applySession(session));
    });
  },

  clearMessages: () => set({ error: null, info: null }),

  signIn: async (email, password) => {
    set({ loading: true, error: null, info: null });
    const localOnly = !isDevAuthBypass() && !getSupabaseClient();
    if (!localOnly && !isValidEmail(email, { allowDevLocalhost: isDevAuthBypass() })) {
      set({ loading: false, error: 'Informe um e-mail válido.' });
      return false;
    }
    if (password.length < 8) {
      set({ loading: false, error: 'A senha deve ter pelo menos 8 caracteres.' });
      return false;
    }
    if (isDevAuthBypass()) {
      set({ loading: false, user: DEV_BYPASS_USER, info: 'Bypass de desenvolvimento ativo.' });
      return true;
    }
    const client = getSupabaseClient();
    if (!client) {
      const result = await signInLocal(email, password);
      if (!result.ok) {
        set({ loading: false, error: result.error });
        return false;
      }
      const local = getLocalSession();
      const session = local ? localSessionAsSupabase(local) : null;
      set({ loading: false, session, user: session?.user ?? null, error: null });
      return true;
    }
    const { data, error } = await client.auth.signInWithPassword({
      email: email.trim(),
      password,
    });
    if (error) {
      set({ loading: false, error: mapAuthError(error) });
      return false;
    }
    set({ loading: false, ...applySession(data.session), error: null });
    return true;
  },

  signUp: async (email, password) => {
    set({ loading: true, error: null, info: null });
    if (!isValidEmail(email, { allowDevLocalhost: isDevAuthBypass() })) {
      set({ loading: false, error: 'Informe um e-mail válido.' });
      return false;
    }
    if (password.length < 8) {
      set({ loading: false, error: 'A senha deve ter pelo menos 8 caracteres.' });
      return false;
    }
    if (isDevAuthBypass()) {
      set({ loading: false, info: 'Bypass de desenvolvimento ativo — cadastro ignorado.' });
      return true;
    }
    const client = getSupabaseClient();
    if (!client) {
      set({ loading: false, error: getSupabaseInitError() });
      return false;
    }
    const { data, error } = await client.auth.signUp({
      email: email.trim(),
      password,
      options: { emailRedirectTo: window.location.origin },
    });
    if (error) {
      set({ loading: false, error: mapAuthError(error) });
      return false;
    }
    if (data.user && !data.session) {
      set({
        loading: false,
        info: 'Enviamos um e-mail de confirmação. Abra o link para ativar a conta.',
      });
      return true;
    }
    set({ loading: false, ...applySession(data.session) });
    return true;
  },

  signInWithGoogle: async () => {
    set({ loading: true, error: null, info: null });
    if (isDevAuthBypass()) {
      set({ loading: false, user: DEV_BYPASS_USER });
      return true;
    }
    const client = getSupabaseClient();
    if (!client) {
      set({ loading: false, error: getSupabaseInitError() });
      return false;
    }
    const { error } = await client.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    });
    if (error) {
      set({ loading: false, error: mapAuthError(error) });
      return false;
    }
    set({ loading: false });
    return true;
  },

  resetPassword: async (email) => {
    set({ loading: true, error: null, info: null });
    if (!isValidEmail(email, { allowDevLocalhost: isDevAuthBypass() })) {
      set({ loading: false, error: 'Informe um e-mail válido.' });
      return false;
    }
    if (isDevAuthBypass()) {
      set({
        loading: false,
        info: 'Bypass de desenvolvimento — e-mail de recuperação não enviado.',
      });
      return true;
    }
    const client = getSupabaseClient();
    if (!client) {
      set({ loading: false, error: getSupabaseInitError() });
      return false;
    }
    const { error } = await client.auth.resetPasswordForEmail(email.trim(), {
      redirectTo: `${window.location.origin}${AUTH_PATHS.reset}`,
    });
    if (error) {
      set({ loading: false, error: mapAuthError(error) });
      return false;
    }
    set({
      loading: false,
      info: 'Se existir uma conta neste e-mail, você receberá o link para redefinir a senha.',
    });
    return true;
  },

  signOut: async () => {
    const client = getSupabaseClient();
    if (client && !isDevAuthBypass()) {
      await client.auth.signOut();
    }
    clearLocalSession();
    set({
      session: null,
      user: isDevAuthBypass() ? DEV_BYPASS_USER : null,
      error: null,
      info: null,
    });
  },
}));

export function isAuthenticated(state: Pick<AuthStore, 'user' | 'session'>): boolean {
  return isDevAuthBypass() || state.session !== null || state.user !== null;
}

export function disposeAuthListener(): void {
  stopListening?.();
  stopListening = null;
  initialized = false;
}
