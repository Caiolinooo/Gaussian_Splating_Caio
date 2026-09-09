import { create } from 'zustand';

import {
  ApiError,
  deleteJob,
  getJob,
  listJobs,
  type JobDetail,
  type JobSummary,
} from '../../lib/api';
import { isAuthFailure } from '../../lib/sessionInvalidation';
import {
  subscribeJobEvents,
  type EventsConnectionState,
  type EventTransport,
  type JobEvent,
} from '../../lib/events';
import { applyJobEvent } from './applyEvent';
import { isTerminalState } from './stages';

const MAX_LOG_LINES = 500;

interface JobsStore {
  jobs: JobSummary[];
  listLoading: boolean;
  listError: string | null;
  current: JobDetail | null;
  currentLoading: boolean;
  currentError: string | null;
  events: JobEvent[];
  logs: string[];
  connection: EventsConnectionState;
  transport: EventTransport | null;
  lastEventAt: number | null;
  subscribedJobId: string | null;
  deletingId: string | null;
  fetchList: () => Promise<void>;
  fetchDetail: (jobId: string) => Promise<void>;
  remove: (jobId: string) => Promise<boolean>;
  subscribe: (jobId: string) => void;
  unsubscribe: () => void;
  applyEvent: (event: JobEvent) => void;
}

let unsubscribeEvents: (() => void) | null = null;

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export const useJobsStore = create<JobsStore>((set, get) => ({
  jobs: [],
  listLoading: false,
  listError: null,
  current: null,
  currentLoading: false,
  currentError: null,
  events: [],
  logs: [],
  connection: 'closed',
  transport: null,
  lastEventAt: null,
  subscribedJobId: null,
  deletingId: null,

  fetchList: async () => {
    set({ listLoading: true, listError: null });
    try {
      const jobs = await listJobs();
      set({ jobs, listLoading: false });
    } catch (error) {
      if (error instanceof ApiError && isAuthFailure(error)) {
        set({ listLoading: false, listError: null });
        return;
      }
      set({
        listError: errorMessage(error, 'Não foi possível carregar os jobs.'),
        listLoading: false,
      });
    }
  },

  fetchDetail: async (jobId) => {
    set({ currentLoading: get().current?.job_id !== jobId, currentError: null });
    try {
      const current = await getJob(jobId);
      set({ current, currentLoading: false });
      if (isTerminalState(current.state) && current.error_message) {
        const logs = get().logs;
        if (!logs.includes(current.error_message)) {
          set({ logs: [...logs, current.error_message].slice(-MAX_LOG_LINES) });
        }
      }
    } catch (error) {
      set({
        currentError: errorMessage(error, 'Não foi possível carregar este job.'),
        currentLoading: false,
      });
    }
  },

  remove: async (jobId) => {
    set({ deletingId: jobId });
    try {
      await deleteJob(jobId);
      set({
        jobs: get().jobs.filter((job) => job.job_id !== jobId),
        deletingId: null,
      });
      if (get().current?.job_id === jobId) {
        get().unsubscribe();
        set({ current: null });
      }
      return true;
    } catch (error) {
      set({
        listError: error instanceof ApiError ? error.message : 'Não foi possível excluir o job.',
        deletingId: null,
      });
      return false;
    }
  },

  applyEvent: (event) => {
    const current = get().current;
    const logs = event.message ? [...get().logs, event.message].slice(-MAX_LOG_LINES) : get().logs;
    set({
      events: [...get().events, event].slice(-MAX_LOG_LINES),
      logs,
      lastEventAt: Date.now(),
      current: applyJobEvent(current, event),
    });
    if (isTerminalState(event.state) && unsubscribeEvents) {
      unsubscribeEvents();
      unsubscribeEvents = null;
      set({ connection: 'closed' });
    }
  },

  subscribe: (jobId) => {
    if (get().subscribedJobId === jobId && unsubscribeEvents) {
      return;
    }
    get().unsubscribe();
    set({
      subscribedJobId: jobId,
      events: [],
      logs: [],
      connection: 'connecting',
      transport: 'ws',
    });
    unsubscribeEvents = subscribeJobEvents(jobId, {
      onEvent: (event) => get().applyEvent(event),
      onState: (connection, transport) => {
        const current = get().current;
        if (current?.job_id === jobId && isTerminalState(current.state)) {
          set({ connection: 'closed', transport });
          return;
        }
        set({ connection, transport });
      },
      onFallbackPoll: () => {
        void get().fetchDetail(jobId);
      },
      shouldStopReconnect: () => {
        const current = get().current;
        return current?.job_id === jobId ? isTerminalState(current.state) : false;
      },
    });
    void get()
      .fetchDetail(jobId)
      .then(() => {
        const current = get().current;
        if (get().subscribedJobId !== jobId) {
          return;
        }
        if (current && isTerminalState(current.state)) {
          if (unsubscribeEvents) {
            unsubscribeEvents();
            unsubscribeEvents = null;
          }
          set({ connection: 'closed', transport: null });
        }
      });
  },

  unsubscribe: () => {
    if (unsubscribeEvents) {
      unsubscribeEvents();
      unsubscribeEvents = null;
    }
    set({ subscribedJobId: null, connection: 'closed', transport: null });
  },
}));
