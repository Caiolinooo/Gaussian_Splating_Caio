import { describe, expect, it } from 'vitest';

import { blendModeLabelPt, overlayKindLabelPt } from './overlayPersist';

describe('labels pt-BR de overlay', () => {
  it('traduz modos de mistura', () => {
    expect(blendModeLabelPt('normal')).toBe('Normal');
    expect(blendModeLabelPt('multiply')).toBe('Multiplicar');
    expect(blendModeLabelPt('overlay')).toBe('Sobrepor');
  });

  it('traduz tipos', () => {
    expect(overlayKindLabelPt('paint')).toBe('Pintura');
  });
});
