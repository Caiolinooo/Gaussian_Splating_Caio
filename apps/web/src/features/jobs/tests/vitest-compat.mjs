import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

export { describe, it };

function matchers(actual) {
  return {
    toBe(expected) {
      assert.strictEqual(actual, expected);
    },
    toEqual(expected) {
      assert.deepEqual(actual, expected);
    },
    toBeNull() {
      assert.equal(actual, null);
    },
    toBeCloseTo(expected, precision = 2) {
      const tol = 10 ** -precision / 2;
      assert.ok(Math.abs(Number(actual) - expected) < tol);
    },
    toMatch(expected) {
      assert.match(String(actual), expected instanceof RegExp ? expected : new RegExp(expected));
    },
    toHaveLength(n) {
      assert.equal(actual.length, n);
    },
    toBeGreaterThan(n) {
      assert.ok(Number(actual) > n);
    },
    toBeTruthy() {
      assert.ok(actual);
    },
    toBeFalsy() {
      assert.ok(!actual);
    },
    toBeUndefined() {
      assert.equal(actual, undefined);
    },
    not: {
      toBeNull() {
        assert.notEqual(actual, null);
      },
      toBe(expected) {
        assert.notStrictEqual(actual, expected);
      },
    },
  };
}

export function expect(actual) {
  return matchers(actual);
}
