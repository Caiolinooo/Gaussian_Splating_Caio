import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  LOCAL_AUTH_STORAGE_KEY,
  LOGIN_PATH,
  SUPABASE_AUTH_STORAGE_KEY,
  clearClientAuthStorage,
  invalidateClientSession,
  isAuthFailure,
} from './sessionInvalidation';

class MemoryStorage {
  private map = new Map<string, string>();

  getItem(key: string): string | null {
    return this.map.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.map.set(key, value);
  }

  removeItem(key: string): void {
    this.map.delete(key);
  }

  clear(): void {
    this.map.clear();
  }
}

vi.stubGlobal('localStorage', new MemoryStorage());

describe('isAuthFailure', () => {
  it('trata 401 UNAUTHENTICATED e TOKEN_INVALID', () => {
    expect(isAuthFailure({ status: 401, errorCode: 'UNAUTHENTICATED' })).toBe(true);
    expect(isAuthFailure({ status: 401, errorCode: 'TOKEN_INVALID' })).toBe(true);
    expect(isAuthFailure({ status: 401, errorCode: 'TOKEN_EXPIRED' })).toBe(true);
    expect(isAuthFailure({ status: 401 })).toBe(true);
  });

  it('não trata senha errada nem 403', () => {
    expect(isAuthFailure({ status: 401, errorCode: 'INVALID_CREDENTIALS' })).toBe(false);
    expect(isAuthFailure({ status: 403, errorCode: 'FORBIDDEN' })).toBe(false);
    expect(isAuthFailure({ status: 404, errorCode: 'UNAUTHENTICATED' })).toBe(false);
  });
});

describe('invalidateClientSession', () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
    vi.stubGlobal('localStorage', new MemoryStorage());
  });

  it('apaga gs-local-auth e gs-auth', () => {
    localStorage.setItem(LOCAL_AUTH_STORAGE_KEY, '{"access_token":"x"}');
    localStorage.setItem(SUPABASE_AUTH_STORAGE_KEY, '{"access_token":"y"}');
    clearClientAuthStorage();
    expect(localStorage.getItem(LOCAL_AUTH_STORAGE_KEY)).toBeNull();
    expect(localStorage.getItem(SUPABASE_AUTH_STORAGE_KEY)).toBeNull();
  });

  it('redireciona para /login fora da tela de login', () => {
    const replace = vi.fn();
    vi.stubGlobal('window', {
      location: { pathname: '/jobs', replace },
    });
    invalidateClientSession();
    expect(replace).toHaveBeenCalledWith(LOGIN_PATH);
  });

  it('não redireciona se já está em /login', () => {
    const replace = vi.fn();
    vi.stubGlobal('window', {
      location: { pathname: '/login', replace },
    });
    invalidateClientSession();
    expect(replace).not.toHaveBeenCalled();
  });
});
