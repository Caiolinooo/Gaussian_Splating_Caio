import { describe, expect, it } from 'vitest';

import {
  asDisplayPercent,
  buildTimeline,
  estimateEtaSeconds,
  isTerminalState,
  jobStateLabel,
  remainingEtaLabel,
} from '../stages';

describe('jobStateLabel', () => {
  it('rotula estados em pt-BR', () => {
    expect(jobStateLabel('autocal')).toMatch(/escala/i);
    expect(jobStateLabel('done')).toBe('Concluído');
  });
});

describe('isTerminalState', () => {
  it('marca done/error/cancelled', () => {
    expect(isTerminalState('done')).toBe(true);
    expect(isTerminalState('error')).toBe(true);
    expect(isTerminalState('training')).toBe(false);
  });
});

describe('estimateEtaSeconds', () => {
  it('estima pelo progresso decorrido', () => {
    const eta = estimateEtaSeconds(60_000, 0.5);
    expect(eta).toBe(60);
  });

  it('devolve nulo sem progresso', () => {
    expect(estimateEtaSeconds(10_000, 0)).toBeNull();
  });
});

describe('remainingEtaLabel', () => {
  it('esconde o ETA em estados terminais', () => {
    expect(remainingEtaLabel('error', 120)).toBeNull();
    expect(remainingEtaLabel('cancelled', 30)).toBeNull();
    expect(remainingEtaLabel('done', 0)).toBeNull();
  });

  it('formata o ETA enquanto o job corre', () => {
    expect(remainingEtaLabel('training', 120)).toMatch(/min/);
  });
});

describe('buildTimeline', () => {
  it('marca extração como pulada em conjunto de imagens', () => {
    const items = buildTimeline({}, 'queued', 'images');
    const extracting = items.find((item) => item.key === 'extracting');
    expect(extracting?.status).toBe('skipped');
    expect(items[0]?.key).toBe('upload');
  });

  it('usa o progresso da etapa corrente', () => {
    const items = buildTimeline(
      { training: { status: 'running', progress: 0.4, message: 'step 4k' } },
      'training',
      'video',
    );
    const training = items.find((item) => item.key === 'training');
    expect(training?.progress).toBe(0.4);
    expect(training?.detail).toBe('step 4k');
  });
});

describe('asDisplayPercent', () => {
  it('converte fração e porcentagem', () => {
    expect(asDisplayPercent(0.255)).toBe(26);
    expect(asDisplayPercent(80)).toBe(80);
  });
});
