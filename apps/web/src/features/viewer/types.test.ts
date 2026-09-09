import { describe, expect, it } from 'vitest';

import { isWorkspaceTool } from './types';

describe('isWorkspaceTool', () => {
  it('aceita órbita, trena, edição e overlays', () => {
    expect(isWorkspaceTool('orbit')).toBe(true);
    expect(isWorkspaceTool('tape')).toBe(true);
    expect(isWorkspaceTool('edit')).toBe(true);
    expect(isWorkspaceTool('overlay')).toBe(true);
    expect(isWorkspaceTool('calibration')).toBe(false);
  });
});
