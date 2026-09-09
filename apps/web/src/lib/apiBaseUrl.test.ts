import { describe, expect, it } from 'vitest';

import { apiConnectionErrorMessage, isLoopbackApiUrl, resolveApiBaseUrl } from './api';

describe('resolveApiBaseUrl', () => {
  it('no Vite :5173 usa VITE_API_URL ou localhost:8000', () => {
    expect(resolveApiBaseUrl({ port: '5173' })).toBe('http://localhost:8000');
    expect(
      resolveApiBaseUrl({
        envUrl: 'http://localhost:8000/',
        origin: 'http://localhost:5173',
        port: '5173',
      }),
    ).toBe('http://localhost:8000');
  });

  it('build servido na API ignora localhost:8000 e usa a origem da página', () => {
    expect(
      resolveApiBaseUrl({
        envUrl: 'http://localhost:8000',
        origin: 'http://vm.groupabz.com:2222',
        port: '2222',
      }),
    ).toBe('http://vm.groupabz.com:2222');
    expect(
      resolveApiBaseUrl({
        envUrl: 'http://127.0.0.1:8000',
        origin: 'http://127.0.0.1:2222',
        port: '2222',
      }),
    ).toBe('http://127.0.0.1:2222');
  });

  it('respeita uma API remota explícita fora do Vite', () => {
    expect(
      resolveApiBaseUrl({
        envUrl: 'https://api.example.com',
        origin: 'https://app.example.com',
        port: '',
      }),
    ).toBe('https://api.example.com');
  });
});

describe('apiConnectionErrorMessage', () => {
  it('cita a URL real e a porta dela — nunca assume 8000', () => {
    const message = apiConnectionErrorMessage('http://vm.groupabz.com:2222');
    expect(message).toContain('http://vm.groupabz.com:2222');
    expect(message).toContain('porta 2222');
    expect(message).not.toContain('porta 8000');
  });

  it('reconhece URL loopback bakeada', () => {
    expect(isLoopbackApiUrl('http://localhost:8000')).toBe(true);
    expect(isLoopbackApiUrl('https://vm.groupabz.com:2222')).toBe(false);
  });
});
