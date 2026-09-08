import { beforeEach, describe, expect, it, vi } from 'vitest';

import { clearLocalSession, getLocalSession, localSessionAsSupabase } from './localAuth';

const STORE_KEY = 'gs-local-auth';

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

function plantSession(expiresInS = 3600): void {
  localStorage.setItem(
    STORE_KEY,
    JSON.stringify({
      access_token: 'token-abc',
      expires_at: Math.floor(Date.now() / 1000) + expiresInS,
      user: { id: 'caio', email: null },
    }),
  );
}

describe('localAuth storage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('devolve null quando não há sessão', () => {
    expect(getLocalSession()).toBeNull();
  });

  it('lê sessão válida e converte para o formato Supabase', () => {
    plantSession();
    const session = getLocalSession();
    expect(session?.user.id).toBe('caio');
    const asSupabase = localSessionAsSupabase(session!);
    expect(asSupabase.access_token).toBe('token-abc');
    expect(asSupabase.user.id).toBe('caio');
  });

  it('descarta sessão expirada', () => {
    plantSession(-10);
    expect(getLocalSession()).toBeNull();
    expect(localStorage.getItem(STORE_KEY)).toBeNull();
  });

  it('ignora JSON inválido', () => {
    localStorage.setItem(STORE_KEY, '{quebrado');
    expect(getLocalSession()).toBeNull();
  });

  it('clearLocalSession remove a chave', () => {
    plantSession();
    clearLocalSession();
    expect(getLocalSession()).toBeNull();
  });
});
