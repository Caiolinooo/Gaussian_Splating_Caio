/** Falha de compilação se um switch sobre union não for exaustivo. */
export function assertNever(value: never, message?: string): never {
  throw new Error(message ?? `Valor inesperado: ${String(value)}`);
}
