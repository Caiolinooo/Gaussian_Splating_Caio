import { describe, expect, it } from 'vitest';

import { isMissingSplatArtifact, MISSING_SPLAT_USER_MESSAGE, ViewerApiError } from './viewerApi';

describe('isMissingSplatArtifact', () => {
  it('reconhece 404 de artefato', () => {
    const error = new ViewerApiError(MISSING_SPLAT_USER_MESSAGE, '/jobs/x/artifacts/ksplat', 404);
    expect(isMissingSplatArtifact(error)).toBe(true);
    expect(error.message).toMatch(/splat/i);
  });

  it('ignora outros erros', () => {
    expect(isMissingSplatArtifact(new Error('falha'))).toBe(false);
    expect(isMissingSplatArtifact(new ViewerApiError('rede', '/jobs/x', 500))).toBe(false);
  });
});
