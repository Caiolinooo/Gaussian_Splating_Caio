import { describe, expect, it } from 'vitest';

import { isValidEmail, mapAuthError } from './authErrors';

describe('mapAuthError', () => {
  it('traduz invalid_credentials', () => {
    expect(mapAuthError({ code: 'invalid_credentials' })).toMatch(/incorretos/);
  });

  it('traduz heurística de mensagem em inglês', () => {
    expect(mapAuthError({ message: 'User already registered' })).toMatch(/já existe/i);
  });
});

describe('isValidEmail', () => {
  it('aceita e-mail simples', () => {
    expect(isValidEmail('pessoa@exemplo.com')).toBe(true);
  });

  it('rejeita vazio e sem domínio', () => {
    expect(isValidEmail('')).toBe(false);
    expect(isValidEmail('pessoa@')).toBe(false);
  });

  it('rejeita dev@localhost fora do bypass', () => {
    expect(isValidEmail('dev@localhost')).toBe(false);
  });

  it('aceita dev@localhost no bypass de desenvolvimento', () => {
    expect(isValidEmail('dev@localhost', { allowDevLocalhost: true })).toBe(true);
    expect(isValidEmail('pessoa@exemplo.com', { allowDevLocalhost: true })).toBe(true);
    expect(isValidEmail('pessoa@', { allowDevLocalhost: true })).toBe(false);
  });
});
