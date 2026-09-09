import { describe, expect, it } from 'vitest';

import { titleForPath } from './pageTitle';

describe('titleForPath', () => {
  it('rotula as rotas principais em pt-BR', () => {
    expect(titleForPath('/login')).toBe('Gaussian Splatting — Entrar');
    expect(titleForPath('/jobs')).toBe('Gaussian Splatting — Jobs');
    expect(titleForPath('/jobs/abc')).toBe('Gaussian Splatting — Acompanhamento do job');
    expect(titleForPath('/upload')).toBe('Gaussian Splatting — Novo upload');
    expect(titleForPath('/viewer')).toBe('Gaussian Splatting — Viewer');
    expect(titleForPath('/setup')).toBe('Gaussian Splatting — Configuração do ambiente');
  });
});
