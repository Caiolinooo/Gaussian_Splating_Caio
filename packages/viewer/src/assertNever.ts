/** Falha de compilação se um switch sobre união/enum não for exaustivo. */
export function assertNever(value: never, message?: string): never {
  throw new Error(message ?? `Unexpected value: ${String(value)}`);
}
