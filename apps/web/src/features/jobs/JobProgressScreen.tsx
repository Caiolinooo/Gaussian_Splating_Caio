import { useEffect, useMemo, useState } from 'react';

import { getApiBaseUrl, getAuthHeaders } from '../../lib/api';
import type { EventsConnectionState } from '../../lib/events';
import { explainJobError } from './errorCatalog';
import { useJobsStore } from './jobsStore';
import {
  asDisplayPercent,
  buildTimeline,
  estimateEtaSeconds,
  isTerminalState,
  jobStateLabel,
  remainingEtaLabel,
  stageStatusLabel,
} from './stages';
import type { JobState } from './types';
import { OPEN_SCENE_EVENT, type OpenSceneDetail } from './types';
import './jobs.css';

export interface JobProgressScreenProps {
  jobId: string;
  onOpenScene?: (jobId: string, sceneId?: string | null) => void;
  onBack?: () => void;
}

function connectionLabel(state: EventsConnectionState, jobState?: JobState | null): string {
  if (jobState && isTerminalState(jobState)) {
    return 'Estado final';
  }
  switch (state) {
    case 'live':
      return 'Ao vivo';
    case 'connecting':
      return 'Conectando…';
    case 'reconnecting':
      return 'Reconectando…';
    case 'polling':
      return 'Atualizando por consulta';
    case 'closed':
      return 'Desconectado';
    default: {
      const exhaustive: never = state;
      return String(exhaustive);
    }
  }
}

export function JobProgressScreen({ jobId, onOpenScene, onBack }: JobProgressScreenProps) {
  const {
    current,
    currentLoading,
    currentError,
    logs,
    connection,
    lastEventAt,
    subscribe,
    unsubscribe,
  } = useJobsStore();
  const [logOpen, setLogOpen] = useState(false);
  const [techLogError, setTechLogError] = useState<string | null>(null);
  const [startedAt] = useState(() => Date.now());

  useEffect(() => {
    subscribe(jobId);
    return () => unsubscribe();
  }, [jobId, subscribe, unsubscribe]);

  const job = current?.job_id === jobId ? current : null;
  const timeline = useMemo(
    () => (job ? buildTimeline(job.stages, job.state, job.source_kind) : []),
    [job],
  );

  const overall = useMemo(() => {
    if (!job) {
      return 0;
    }
    const weights: Record<string, number> = {
      extracting: 0.1,
      sfm: 0.18,
      training: 0.47,
      exporting: 0.1,
      meshproxy: 0.05,
      autocal: 0.1,
    };
    let total = 0;
    for (const item of timeline) {
      if (item.key === 'upload') {
        continue;
      }
      const weight = weights[item.key] ?? 0;
      const done =
        item.status === 'done' || item.status === 'skipped' || item.status === 'upload-done';
      total += weight * (done ? 1 : item.progress);
    }
    return total;
  }, [job, timeline]);

  const etaSeconds = job?.eta_seconds ?? estimateEtaSeconds(Date.now() - startedAt, overall);
  const etaLabel = job ? remainingEtaLabel(job.state, etaSeconds) : null;
  const explained =
    job?.state === 'error' ? explainJobError(job.error_code, job.error_message) : null;

  function openScene() {
    const sceneId = job?.scene_id ?? null;
    if (onOpenScene) {
      onOpenScene(jobId, sceneId);
      return;
    }
    const detail: OpenSceneDetail = { jobId, sceneId };
    window.dispatchEvent(new CustomEvent<OpenSceneDetail>(OPEN_SCENE_EVENT, { detail }));
  }

  function downloadLog() {
    const blob = new Blob([logs.join('\n')], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `job-${jobId}-log.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function downloadTechnicalLog() {
    setTechLogError(null);
    try {
      const response = await fetch(
        `${getApiBaseUrl()}/jobs/${encodeURIComponent(jobId)}/artifacts/log`,
        { headers: { Accept: 'text/plain', ...(await getAuthHeaders()) } },
      );
      if (response.status === 404) {
        setTechLogError('Registro técnico do COLMAP ainda não disponível para este job.');
        return;
      }
      if (!response.ok) {
        setTechLogError(`Erro ${response.status} ao baixar o registro técnico.`);
        return;
      }
      const text = await response.text();
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `job-${jobId}-colmap.log`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      setTechLogError('Não foi possível conectar à API para baixar o registro técnico.');
    }
  }

  return (
    <main className="jobs-screen">
      <header className="jobs-header">
        <div>
          <h1>Acompanhamento do processamento</h1>
          <p className="muted">
            Job {jobId}
            {job ? ` · ${jobStateLabel(job.state)}` : ''}
          </p>
          <p className={connection === 'live' ? 'jobs-connection is-live' : 'jobs-connection'}>
            {connectionLabel(connection, job?.state)}
            {lastEventAt
              ? ` · última atualização ${new Date(lastEventAt).toLocaleTimeString('pt-BR')}`
              : ''}
          </p>
        </div>
        <div className="jobs-toolbar">
          {onBack && (
            <button type="button" onClick={onBack}>
              Voltar aos jobs
            </button>
          )}
          {job?.state === 'done' && (
            <button type="button" className="primary" onClick={openScene}>
              Abrir cena
            </button>
          )}
        </div>
      </header>

      {currentError && (
        <div className="error-banner" role="alert">
          <span>{currentError}</span>
        </div>
      )}

      {currentLoading && !job && <p className="muted">Carregando o job…</p>}

      {job && (
        <>
          <div className="progress-area">
            <div
              className="progress-bar"
              role="progressbar"
              aria-valuenow={asDisplayPercent(overall)}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="progress-bar-fill"
                style={{ width: `${asDisplayPercent(overall)}%` }}
              />
            </div>
            <p className="muted">
              {asDisplayPercent(overall)}%
              {etaLabel ? ` · tempo restante: ${etaLabel}` : ''}
            </p>
          </div>

          {explained && (
            <section className="jobs-error-card" aria-labelledby="job-error-title">
              <h2 id="job-error-title">{explained.title}</h2>
              <p>{explained.message}</p>
              <p>
                <strong>O que fazer:</strong> {explained.action}
              </p>
            </section>
          )}

          <ol className="jobs-timeline">
            {timeline.map((item) => (
              <li
                key={item.key}
                className={`jobs-stage status-${item.status === 'upload-done' ? 'done' : item.status}`}
              >
                <div className="jobs-stage-head">
                  <strong>{item.label}</strong>
                  <span className="status-label">
                    {item.status === 'upload-done' ? 'Concluída' : stageStatusLabel(item.status)}
                    {item.status === 'running' ? ` · ${asDisplayPercent(item.progress)}%` : ''}
                  </span>
                </div>
                {item.status === 'running' && (
                  <div className="progress-bar" aria-hidden>
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${asDisplayPercent(item.progress)}%` }}
                    />
                  </div>
                )}
                {item.detail && <p className="jobs-stage-detail">{item.detail}</p>}
              </li>
            ))}
          </ol>

          <div className="log-area">
            <button type="button" onClick={() => setLogOpen((open) => !open)}>
              {logOpen ? 'Ocultar registro' : `Ver registro (${logs.length} linhas)`}
            </button>
            <button type="button" onClick={downloadLog} disabled={logs.length === 0}>
              Baixar registro
            </button>
            <button type="button" onClick={() => void downloadTechnicalLog()}>
              Baixar registro COLMAP
            </button>
            {logOpen && <pre className="jobs-log">{logs.join('\n') || 'Sem registros ainda.'}</pre>}
            {techLogError && <p className="jobs-log-error">{techLogError}</p>}
          </div>
        </>
      )}
    </main>
  );
}
