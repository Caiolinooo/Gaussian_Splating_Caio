import { useEffect, useState } from 'react';

import { useAuthStore } from '../auth/authStore';
import { useJobsStore } from './jobsStore';
import { asDisplayPercent, jobStateLabel, sourceKindLabel } from './stages';
import './jobs.css';

export interface JobsListPageProps {
  onOpenJob?: (jobId: string) => void;
  onNewUpload?: () => void;
  onOpenScene?: (jobId: string) => void;
}

function formatCreatedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
}

export function JobsListPage({ onOpenJob, onNewUpload, onOpenScene }: JobsListPageProps) {
  const { jobs, listLoading, listError, fetchList, remove, deletingId } = useJobsStore();
  const user = useAuthStore((state) => state.user);
  const signOut = useAuthStore((state) => state.signOut);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  useEffect(() => {
    void fetchList();
  }, [fetchList]);

  return (
    <main className="jobs-screen">
      <header className="jobs-header">
        <div>
          <h1>Seus processamentos</h1>
          <p className="muted">Acompanhe o estado, o progresso e reabra cenas já concluídas.</p>
          {user?.email && <p className="jobs-account">{user.email}</p>}
        </div>
        <div className="jobs-toolbar">
          <button type="button" className="primary" onClick={onNewUpload}>
            Novo processamento
          </button>
          <button type="button" onClick={() => void fetchList()} disabled={listLoading}>
            Atualizar
          </button>
          <button type="button" onClick={() => void signOut()}>
            Sair
          </button>
        </div>
      </header>

      {listError && (
        <div className="error-banner" role="alert">
          <span>{listError}</span>
          <button type="button" onClick={() => void fetchList()}>
            Tentar novamente
          </button>
        </div>
      )}

      {listLoading && jobs.length === 0 && <p className="muted">Carregando jobs…</p>}

      {!listLoading && jobs.length === 0 && (
        <div className="jobs-empty">
          <p>Você ainda não enviou nenhum material.</p>
          <button type="button" className="primary" onClick={onNewUpload}>
            Enviar vídeo ou imagens
          </button>
        </div>
      )}

      <ul className="jobs-grid">
        {jobs.map((job) => (
          <li key={job.job_id} className="job-card">
            <div className="job-card-top">
              <strong>{sourceKindLabel(job.source_kind)}</strong>
              <span className="status-label">{jobStateLabel(job.state)}</span>
            </div>
            <p className="job-card-meta">
              {formatCreatedAt(job.created_at)} · {asDisplayPercent(job.progress)}%
            </p>
            <div className="progress-bar" aria-hidden>
              <div
                className="progress-bar-fill"
                style={{ width: `${asDisplayPercent(job.progress)}%` }}
              />
            </div>
            <div className="actions">
              <button type="button" className="primary" onClick={() => onOpenJob?.(job.job_id)}>
                {job.state === 'done' ? 'Reabrir' : 'Acompanhar'}
              </button>
              {job.state === 'done' && (
                <button type="button" onClick={() => onOpenScene?.(job.job_id)}>
                  Abrir cena
                </button>
              )}
              {pendingDelete === job.job_id ? (
                <>
                  <button
                    type="button"
                    disabled={deletingId === job.job_id}
                    onClick={() => void remove(job.job_id).then(() => setPendingDelete(null))}
                  >
                    Confirmar exclusão
                  </button>
                  <button type="button" onClick={() => setPendingDelete(null)}>
                    Cancelar
                  </button>
                </>
              ) : (
                <button type="button" onClick={() => setPendingDelete(job.job_id)}>
                  Excluir
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
