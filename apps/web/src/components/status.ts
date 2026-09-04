import type { CheckStatus, StepStatus } from '../api/types';

/** Rótulo em pt-BR para o estado de uma checagem de componente. */
export function checkStatusLabel(status: CheckStatus): string {
  switch (status) {
    case 'ok':
      return 'OK';
    case 'warning':
      return 'Atenção';
    case 'error':
      return 'Erro';
    case 'missing':
      return 'Ausente';
    case 'unknown':
      return 'Desconhecido';
    default: {
      const exhaustive: never = status;
      throw new Error(`Status de checagem não tratado: ${String(exhaustive)}`);
    }
  }
}

/** Rótulo em pt-BR para o estado de uma etapa do provisionamento. */
export function stepStatusLabel(status: StepStatus): string {
  switch (status) {
    case 'pending':
      return 'Pendente';
    case 'running':
      return 'Em execução';
    case 'done':
      return 'Concluída';
    case 'skipped':
      return 'Pulada (stub)';
    case 'error':
      return 'Erro';
    default: {
      const exhaustive: never = status;
      throw new Error(`Status de etapa não tratado: ${String(exhaustive)}`);
    }
  }
}

/** Ícone textual para qualquer estado exibido na UI de Setup. */
export function statusIcon(status: CheckStatus | StepStatus): string {
  switch (status) {
    case 'ok':
    case 'done':
      return '✓';
    case 'warning':
      return '⚠';
    case 'error':
      return '✕';
    case 'missing':
      return '?';
    case 'unknown':
    case 'pending':
      return '…';
    case 'running':
      return '▶';
    case 'skipped':
      return '↷';
    default: {
      const exhaustive: never = status;
      throw new Error(`Status não tratado: ${String(exhaustive)}`);
    }
  }
}
