import { describe, expect, it } from 'vitest';

import { explainJobError } from '../errorCatalog';

describe('explainJobError', () => {
  it('explica FEW_MATCHES com ação em pt-BR', () => {
    const explained = explainJobError('FEW_MATCHES');
    expect(explained.title).toMatch(/correspondências/i);
    expect(explained.action).toMatch(/textura/i);
  });

  it('prioriza a mensagem da API quando houver', () => {
    const explained = explainJobError('TOO_FEW_FRAMES', 'Só restaram 12 frames nítidos.');
    expect(explained.message).toBe('Só restaram 12 frames nítidos.');
  });

  it('não manda gravar de novo só porque o gate antigo era 150', () => {
    const explained = explainJobError('TOO_FEW_FRAMES');
    expect(explained.title).toMatch(/utilizáveis/i);
    expect(explained.action).not.toMatch(/Grave com mais tempo/i);
    expect(explained.action).toMatch(/8 frames/i);
  });

  it('cai no genérico para código desconhecido', () => {
    const explained = explainJobError('WEIRD', null);
    expect(explained.action).toMatch(/registro/i);
  });

  it('explica COLMAP_FAILED com dica de Setup', () => {
    const explained = explainJobError(
      'COLMAP_FAILED',
      'O COLMAP não está instalado ou não foi encontrado neste ambiente.',
    );
    expect(explained.title).toMatch(/COLMAP/i);
    expect(explained.message).toMatch(/não está instalado/i);
    expect(explained.action).toMatch(/Setup/i);
  });
});
