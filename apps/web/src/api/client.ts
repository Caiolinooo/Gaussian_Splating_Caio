import type { ApiHealth, HealthReport, InstallAccepted, SetupProgress } from './types';

const API_BASE_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/** Erro de comunicação com a API local, com mensagem pronta para a UI (pt-BR). */
export class ApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: 'application/json' },
      ...init,
    });
  } catch {
    throw new ApiError(
      'Não foi possível conectar à API local. Verifique se o backend está em execução (uvicorn na porta 8000).',
    );
  }

  if (!response.ok) {
    let detail = `Erro ${response.status} ao comunicar com a API.`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        detail = body.detail;
      }
    } catch {
      // resposta sem corpo JSON — mantém a mensagem genérica
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<ApiHealth>('/health'),
  setupStatus: () => request<HealthReport>('/setup/status'),
  startInstall: () => request<InstallAccepted>('/setup/install', { method: 'POST' }),
  setupProgress: () => request<SetupProgress>('/setup/progress'),
};
