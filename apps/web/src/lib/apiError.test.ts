import { describe, expect, it } from 'vitest';

import { parseApiErrorBody } from './api';

describe('parseApiErrorBody', () => {
  it('lê o envelope FastAPI {detail:{message,code}} como primário', () => {
    const error = parseApiErrorBody(
      JSON.stringify({ detail: { message: 'Job não encontrado.', code: 'JOB_NOT_FOUND' } }),
      404,
    );
    expect(error.message).toBe('Job não encontrado.');
    expect(error.errorCode).toBe('JOB_NOT_FOUND');
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
