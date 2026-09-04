import { useState, type FormEvent } from 'react';

import { AUTH_PATHS, useAuthStore } from './authStore';
import type { AuthPageProps } from './LoginPage';
import './auth.css';

export function ResetPage({ onNavigate }: AuthPageProps) {
  const { resetPassword, loading, error, info, clearMessages } = useAuthStore();
  const [email, setEmail] = useState('');

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await resetPassword(email);
  }

  return (
    <main className="auth-screen">
      <h1>Redefinir senha</h1>
      <p className="muted">Informe o e-mail da conta. Enviaremos um link se ela existir.</p>
      <form className="auth-card" onSubmit={(event) => void onSubmit(event)}>
        {error && (
          <div className="auth-banner auth-banner-error" role="alert">
            {error}
          </div>
        )}
        {info && (
          <div className="auth-banner auth-banner-info" role="status">
            {info}
          </div>
        )}
        <div className="auth-field">
          <label htmlFor="auth-reset-email">E-mail</label>
          <input
            id="auth-reset-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => {
              clearMessages();
              setEmail(event.target.value);
            }}
            required
          />
        </div>
        <div className="auth-actions">
          <button type="submit" className="primary" disabled={loading}>
            {loading ? 'Enviando…' : 'Enviar link'}
          </button>
        </div>
        <div className="auth-links">
          <a
            href={AUTH_PATHS.login}
            onClick={(event) => {
              if (onNavigate) {
                event.preventDefault();
                onNavigate('login');
              }
            }}
          >
            Voltar ao login
          </a>
        </div>
      </form>
    </main>
  );
}
