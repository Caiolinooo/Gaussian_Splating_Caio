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
});
