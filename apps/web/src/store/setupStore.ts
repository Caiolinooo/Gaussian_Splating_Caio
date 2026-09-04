import { create } from 'zustand';

import { api } from '../api/client';
import type { HealthReport, SetupProgress } from '../api/types';

const POLL_INTERVAL_MS = 1500;

interface SetupStore {
  health: HealthReport | null;
  progress: SetupProgress | null;
  isLoadingHealth: boolean;
  isStartingInstall: boolean;
  error: string | null;
  fetchHealth: () => Promise<void>;
  startInstall: () => Promise<void>;
  refreshProgress: () => Promise<void>;
  startPolling: () => void;
  stopPolling: () => void;
}

let pollTimer: ReturnType<typeof setInterval> | null = null;

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback;
}

export const useSetupStore = create<SetupStore>((set, get) => ({
  health: null,
  progress: null,
  isLoadingHealth: false,
  isStartingInstall: false,
  error: null,

  fetchHealth: async () => {
    set({ isLoadingHealth: true, error: null });
    try {
      const health = await api.setupStatus();
      set({ health, isLoadingHealth: false });
    } catch (err) {
      set({
        error: errorMessage(err, 'Erro inesperado ao verificar o ambiente.'),
        isLoadingHealth: false,
      });
    }
  },

  startInstall: async () => {
    set({ isStartingInstall: true, error: null });
    try {
      await api.startInstall();
      await get().refreshProgress();
    } catch (err) {
      set({ error: errorMessage(err, 'Erro inesperado ao iniciar a instalação.') });
    } finally {
      set({ isStartingInstall: false });
    }
  },

  refreshProgress: async () => {
    try {
      const progress = await api.setupProgress();
      set({ progress });
    } catch (err) {
      set({ error: errorMessage(err, 'Erro ao consultar o progresso do provisionamento.') });
      get().stopPolling();
    }
  },

  startPolling: () => {
    if (pollTimer !== null) {
      return;
    }
    pollTimer = setInterval(() => {
      void get().refreshProgress();
    }, POLL_INTERVAL_MS);
  },

  stopPolling: () => {
    if (pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  },
}));
