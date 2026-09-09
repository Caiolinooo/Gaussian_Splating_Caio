import { describe, expect, it } from 'vitest';

import { resolveDevAuthBypass } from './supabase';

describe('resolveDevAuthBypass', () => {
  it('só liga com flag 1 em hostname loopback', () => {
    expect(resolveDevAuthBypass('1', 'localhost')).toBe(true);
    expect(resolveDevAuthBypass('1', '127.0.0.1')).toBe(true);
    expect(resolveDevAuthBypass('1', '[::1]')).toBe(true);
  });

  it('nunca liga no servidor remoto mesmo com flag 1', () => {
    expect(resolveDevAuthBypass('1', 'vm.groupabz.com')).toBe(false);
    expect(resolveDevAuthBypass('1', 'example.com')).toBe(false);
  });

  it('fica off sem flag 1', () => {
    expect(resolveDevAuthBypass('0', 'localhost')).toBe(false);
    expect(resolveDevAuthBypass(undefined, 'localhost')).toBe(false);
    expect(resolveDevAuthBypass('', 'localhost')).toBe(false);
  });
});
