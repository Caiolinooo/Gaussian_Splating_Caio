import { describe, expect, it } from 'vitest';

import { parseApiErrorBody } from './api';
import { isAuthFailure } from './sessionInvalidation';

describe('parseApiErrorBody', () => {
  it('lê o envelope FastAPI {detail:{message,code}} como primário', () => {
    const error = parseApiErrorBody(
      JSON.stringify({ detail: { message: 'Job não encontrado.', code: 'JOB_NOT_FOUND' } }),
      404,
    );
    expect(error.message).toBe('Job não encontrado.');
    expect(error.errorCode).toBe('JOB_NOT_FOUND');
  });

  it('lê Token inválido / UNAUTHENTICATED como falha de sessão', () => {
    const invalid = parseApiErrorBody(
      JSON.stringify({ detail: { message: 'Token inválido.', code: 'TOKEN_INVALID' } }),
      401,
    );
    expect(invalid.message).toBe('Token inválido.');
    expect(isAuthFailure(invalid)).toBe(true);

    const missing = parseApiErrorBody(
      JSON.stringify({
        detail: { message: 'Não autenticado. Envie um token Bearer válido.', code: 'UNAUTHENTICATED' },
      }),
      401,
    );
    expect(isAuthFailure(missing)).toBe(true);
  });

  it('ainda aceita o formato legado {error_code,message}', () => {
    const error = parseApiErrorBody(
      JSON.stringify({ error_code: 'FORBIDDEN', message: 'Acesso negado.' }),
      403,
    );
    expect(error.message).toBe('Acesso negado.');
    expect(error.errorCode).toBe('FORBIDDEN');
  });
});
