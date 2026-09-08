import { useEffect, useState } from 'react';

import { useSetupStore } from '../store/setupStore';
import { AppChrome } from './AppShell';
import { checkStatusLabel, statusIcon, stepStatusLabel } from './status';

/** Tela inicial: UI de Setup do Provisioner (relatório de saúde + progresso da instalação). */
export function SetupScreen() {
  const {
    health,
    progress,
    isLoadingHealth,
    isStartingInstall,
    error,
    fetchHealth,
    startInstall,
    refreshProgress,
    startPolling,
    stopPolling,
  } = useSetupStore();
  const [logOpen, setLogOpen] = useState(false);

  useEffect(() => {
    void fetchHealth();
    void refreshProgress();
    startPolling();
    return () => stopPolling();
  }, [fetchHealth, refreshProgress, startPolling, stopPolling]);

  const isRunning = progress?.state === 'running';
  const steps = progress?.steps ?? [];
  const logLines = progress?.log ?? [];
  const hasSkippedSteps = steps.some((step) => step.status === 'skipped');

  function downloadLog() {
    const blob = new Blob([logLines.join('\n')], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `setup-log-${new Date().toISOString().replace(/[:.]/g, '-')}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <AppChrome>
    <main className="setup-screen">
      <header className="setup-header">
        <h1>Configuração do ambiente</h1>
        <p>
          O Provisioner verifica e prepara automaticamente tudo o que o pipeline de Gaussian
          Splatting precisa — você não precisa executar nenhum comando manualmente.
        </p>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => void fetchHealth()}>
            Tentar novamente
          </button>
        </div>
      )}

      <section aria-labelledby="health-title">
        <h2 id="health-title">Relatório de saúde do ambiente</h2>
        {isLoadingHealth && !health ? (
          <p className="muted">Verificando o ambiente…</p>
        ) : health ? (
          <>
            <p className={`overall status-${health.overall}`}>
              {health.ready
                ? 'Ambiente pronto para o pipeline.'
                : 'Há pendências no ambiente — veja as ações guiadas abaixo.'}
            </p>
            <ul className="health-grid">
              {health.checks.map((check) => (
                <li key={check.key} className={`health-card status-${check.status}`}>
                  <div className="health-card-header">
                    <span className="status-icon" aria-hidden>
                      {statusIcon(check.status)}
                    </span>
                    <strong>{check.name}</strong>
                    <span className="status-label">{checkStatusLabel(check.status)}</span>
                  </div>
                  <p>{check.message}</p>
                  {check.fix_hint && (
                    <p className="fix-hint">
                      <strong>Como resolver:</strong> {check.fix_hint}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="muted">Relatório indisponível — verifique a conexão com a API.</p>
        )}
      </section>

      <section aria-labelledby="progress-title">
        <h2 id="progress-title">Provisionamento</h2>
        <div className="actions">
          <button
            type="button"
            className="primary"
            disabled={isRunning || isStartingInstall}
            onClick={() => void startInstall()}
          >
            {isRunning || isStartingInstall
              ? 'Instalação em andamento…'
              : 'Iniciar instalação automática'}
          </button>
          <button type="button" disabled={isLoadingHealth} onClick={() => void fetchHealth()}>
            Verificar ambiente novamente
          </button>
        </div>

        {progress && progress.state !== 'idle' && (
          <div className="progress-area">
            <div
              className="progress-bar"
              role="progressbar"
              aria-valuenow={progress.percent}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div className="progress-bar-fill" style={{ width: `${progress.percent}%` }} />
            </div>
            <p className="muted">{progress.percent}% concluído</p>

            <ol className="steps-list">
              {steps.map((step) => (
                <li key={step.key} className={`step status-${step.status}`}>
                  <span className="status-icon" aria-hidden>
                    {statusIcon(step.status)}
                  </span>
                  <span className="step-title">{step.title}</span>
                  <span className="status-label">{stepStatusLabel(step.status)}</span>
                  {step.detail && <p className="step-detail">{step.detail}</p>}
                </li>
              ))}
            </ol>

            {hasSkippedSteps && (
              <p className="muted">
                As etapas marcadas como “puladas” são stubs da Fase 0 — a instalação real de cada
                componente chega na próxima fase, e o plano completo fica registrado no log.
              </p>
            )}

            <div className="log-area">
              <button type="button" onClick={() => setLogOpen((open) => !open)}>
                {logOpen ? 'Ocultar registro' : `Ver registro (${logLines.length} linhas)`}
              </button>
              <button type="button" onClick={downloadLog} disabled={logLines.length === 0}>
                Baixar registro para suporte
              </button>
              {logOpen && (
                <pre className="log-view">{logLines.join('\n') || 'Sem registros ainda.'}</pre>
              )}
            </div>
          </div>
        )}
      </section>
    </main>
    </AppChrome>
  );
}
