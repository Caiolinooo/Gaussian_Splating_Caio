import { useEffect, useMemo, useRef, useState } from 'react';

import { formatHeightMeters, heightInputToMeters, validateHeightMeters } from './height';
import { MEDIA_ACCEPT } from './constants';
import { isHeicFile } from './validation';
import { useUploadStore } from './uploadStore';
import './jobs.css';

export interface UploadWizardProps {
  onSubmitted?: (jobId: string) => void;
  onCancel?: () => void;
}

export function UploadWizard({ onSubmitted, onCancel }: UploadWizardProps) {
  const store = useUploadStore();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const objectUrls = useMemo(
    () => store.files.map((file) => ({ file, url: URL.createObjectURL(file) })),
    [store.files],
  );

  useEffect(() => {
    return () => {
      for (const item of objectUrls) {
        URL.revokeObjectURL(item.url);
      }
    };
  }, [objectUrls]);

  const meters = heightInputToMeters(store.heightInput());
  const liveHeightError = store.step === 2 ? validateHeightMeters(meters) : null;
  const canContinue =
    store.fileErrors.length === 0 &&
    store.files.length > 0 &&
    store.sourceKind !== null &&
    !store.mediaProbing;

  async function goNext() {
    const ok = await store.probeMedia();
    if (ok) {
      store.goToStep(2);
    }
  }

  async function onSubmit() {
    const jobId = await store.submit();
    if (jobId) {
      onSubmitted?.(jobId);
    }
  }

  return (
    <main className="jobs-screen">
      <header className="jobs-header">
        <div>
          <h1>Novo processamento</h1>
          <p className="muted">
            Envie um vídeo, um GIF, um PLY ou um conjunto de imagens e informe a sua altura.
          </p>
        </div>
        {onCancel && (
          <button type="button" onClick={onCancel}>
            Cancelar
          </button>
        )}
      </header>

      <ol className="jobs-stepper">
        <li className={store.step === 1 ? 'is-active' : 'is-done'}>1. Arquivos</li>
        <li className={store.step === 2 ? 'is-active' : undefined}>2. Altura</li>
      </ol>

      {store.step === 1 && (
        <section className="jobs-wizard" aria-labelledby="upload-files-title">
          <h2 id="upload-files-title">Vídeo, GIF, PLY ou imagens</h2>
          <label
            className={dragOver ? 'jobs-drop is-over' : 'jobs-drop'}
            onDragOver={(event) => {
              event.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragOver(false);
              store.setFiles(Array.from(event.dataTransfer.files));
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept={MEDIA_ACCEPT}
              multiple
              onChange={(event) => {
                store.setFiles(Array.from(event.target.files ?? []));
              }}
            />
            <strong>Arraste o arquivo aqui</strong>
            <p className="muted">
              Vídeo MP4/MOV/WEBM, GIF (frames), PLY (splat pronto, sem SfM) ou pelo menos 20 fotos
              JPG/PNG/HEIC.
            </p>
          </label>

          {store.sourceKind === 'video' && objectUrls[0] && (
            <div className="jobs-video-preview">
              <video src={objectUrls[0].url} controls preload="metadata" />
              <span className="jobs-preview-name">{objectUrls[0].file.name}</span>
            </div>
          )}

          {store.sourceKind === 'gif' && objectUrls[0] && (
            <div className="jobs-video-preview">
              <img src={objectUrls[0].url} alt={objectUrls[0].file.name} />
              <span className="jobs-preview-name">{objectUrls[0].file.name}</span>
            </div>
          )}

          {store.sourceKind === 'ply' && objectUrls[0] && (
            <p className="jobs-preview-name">Splat pronto: {objectUrls[0].file.name}</p>
          )}

          {store.sourceKind === 'images' && (
            <ul className="jobs-preview-grid">
              {objectUrls.map((item, index) => (
                <li key={`${item.file.name}-${index}`}>
                  {isHeicFile(item.file) ? (
                    <span className="jobs-preview-name">Prévia indisponível (HEIC)</span>
                  ) : (
                    <img src={item.url} alt={item.file.name} />
                  )}
                  <span className="jobs-preview-name">{item.file.name}</span>
                  <button
                    type="button"
                    className="jobs-preview-remove"
                    onClick={() => store.removeFile(index)}
                  >
                    Remover
                  </button>
                </li>
              ))}
            </ul>
          )}

          {store.fileErrors.length > 0 && (
            <ul className="jobs-errors" role="alert">
              {store.fileErrors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          )}

          <div className="actions">
            <button
              type="button"
              className="primary"
              disabled={!canContinue}
              onClick={() => void goNext()}
            >
              {store.mediaProbing ? 'Validando arquivos…' : 'Continuar'}
            </button>
            {store.files.length > 0 && (
              <button type="button" onClick={() => store.clearFiles()}>
                Limpar seleção
              </button>
            )}
          </div>
        </section>
      )}

      {store.step === 2 && (
        <section className="jobs-wizard" aria-labelledby="upload-height-title">
          <h2 id="upload-height-title">Sua altura</h2>
          <p className="muted">
            Usamos este valor para estimar a escala real da cena (auto-calibração). Você poderá
            confirmar ou ajustar depois no viewer.
          </p>

          <label className="jobs-field">
            Sistema
            <select
              value={store.heightSystem}
              onChange={(event) =>
                store.setHeightSystem(event.target.value === 'imperial' ? 'imperial' : 'metric')
              }
            >
              <option value="metric">Metros / centímetros</option>
              <option value="imperial">Pés / polegadas</option>
            </select>
          </label>

          {store.heightSystem === 'metric' ? (
            <div className="jobs-height-grid">
              <label>
                Metros
                <input
                  inputMode="decimal"
                  value={store.metricMeters}
                  onChange={(event) => store.setMetricMeters(event.target.value)}
                  placeholder="1,75"
                />
              </label>
              <label>
                Centímetros extras
                <input
                  inputMode="decimal"
                  value={store.metricCentimeters}
                  onChange={(event) => store.setMetricCentimeters(event.target.value)}
                  placeholder="0"
                />
              </label>
            </div>
          ) : (
            <div className="jobs-height-grid">
              <label>
                Pés
                <input
                  inputMode="decimal"
                  value={store.imperialFeet}
                  onChange={(event) => store.setImperialFeet(event.target.value)}
                  placeholder="5"
                />
              </label>
              <label>
                Polegadas
                <input
                  inputMode="decimal"
                  value={store.imperialInches}
                  onChange={(event) => store.setImperialInches(event.target.value)}
                  placeholder="9"
                />
              </label>
            </div>
          )}

          {meters !== null && (
            <p className="jobs-live-convert">
              Você informou: <strong>{formatHeightMeters(meters, 'metric')}</strong>
              {' · '}
              <strong>{formatHeightMeters(meters, 'imperial')}</strong>
            </p>
          )}

          {(liveHeightError || store.heightError) && (
            <p className="jobs-errors" role="alert">
              {store.heightError ?? liveHeightError}
            </p>
          )}

          {store.submitError && (
            <p className="jobs-errors" role="alert">
              {store.submitError}
            </p>
          )}

          {store.submitting && (
            <div className="progress-area">
              <div
                className="progress-bar"
                role="progressbar"
                aria-valuenow={store.uploadPercent}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div className="progress-bar-fill" style={{ width: `${store.uploadPercent}%` }} />
              </div>
              <p className="muted">Enviando arquivos… {store.uploadPercent}%</p>
            </div>
          )}

          <div className="actions">
            <button type="button" onClick={() => store.goToStep(1)} disabled={store.submitting}>
              Voltar
            </button>
            <button
              type="button"
              className="primary"
              disabled={store.submitting || Boolean(liveHeightError)}
              onClick={() => void onSubmit()}
            >
              {store.submitting ? 'Enviando…' : 'Enviar para processamento'}
            </button>
          </div>
        </section>
      )}
    </main>
  );
}
