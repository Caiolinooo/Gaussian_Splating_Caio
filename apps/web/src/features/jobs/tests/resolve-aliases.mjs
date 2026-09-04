const units = new URL('../../../../../../packages/units/src/index.ts', import.meta.url).href;
const vitest = new URL('./vitest-compat.mjs', import.meta.url).href;

export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'vitest') {
    return { url: vitest, shortCircuit: true };
  }
  if (specifier === '@gs/units') {
    return { url: units, shortCircuit: true };
  }
  if (specifier.startsWith('.') && !/\.[cm]?[jt]sx?$/.test(specifier)) {
    return nextResolve(`${specifier}.ts`, context);
  }
  return nextResolve(specifier, context);
}
