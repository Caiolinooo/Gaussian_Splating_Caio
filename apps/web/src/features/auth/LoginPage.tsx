import { useEffect, useState, type FormEvent, type MouseEvent } from 'react';

import { AUTH_PATHS, useAuthStore } from './authStore';
import './auth.css';

export interface AuthPageProps {
  onAuthenticated?: () => void;
  onNavigate?: (page: 'login' | 'signup' | 'reset') => void;
}

function followLink(
  event: MouseEvent<HTMLAnchorElement>,
  page: 'login' | 'signup' | 'reset',
  onNavigate?: AuthPageProps['onNavigate'],
): void {
  if (onNavigate) {
    event.preventDefault();
    onNavigate(page);
  }
}

export function LoginPage({ onAuthenticated, onNavigate }: AuthPageProps) {
  const {
    signIn,
    signInWithGoogle,
    loading,
    error,
    info,
    clearMessages,
    localAuthEnabled,
    defaultUsername,
  } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  useEffect(() => {
    if (defaultUsername) {
      setEmail((current) => current || defaultUsername);
    }
  }, [defaultUsername]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const ok = await signIn(email, password);
    if (ok) {
      onAuthenticated?.();
    }
  }

  return (
    <main className="auth-screen">
      <h1>Entrar</h1>
      <p className="muted">Acesse sua conta para enviar vídeos e acompanhar os processamentos.</p>
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
          <label htmlFor="auth-login-email">
            {localAuthEnabled ? 'Usuário ou e-mail' : 'E-mail'}
          </label>
          <input
            id="auth-login-email"
            type="text"
            inputMode="email"
            autoComplete="username"
            value={email}
            onChange={(event) => {
              clearMessages();
              setEmail(event.target.value);
            }}
            required
          />
        </div>
        <div className="auth-field">
          <label htmlFor="auth-login-password">Senha</label>
          <input
            id="auth-login-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => {
              clearMessages();
              setPassword(event.target.value);
            }}
            required
            minLength={8}
          />
        </div>
        <div className="auth-actions">
          <button type="submit" className="primary" disabled={loading}>
            {loading ? 'Entrando…' : 'Entrar'}
          </button>
          {!localAuthEnabled && (
            <>
              <div className="auth-divider">ou</div>
              <button type="button" disabled={loading} onClick={() => void signInWithGoogle()}>
                Continuar com Google
              </button>
            </>
          )}
        </div>
        {!localAuthEnabled && (
          <div className="auth-links">
            <a
              href={AUTH_PATHS.signup}
              onClick={(event) => followLink(event, 'signup', onNavigate)}
            >
              Criar conta
            </a>
            <a href={AUTH_PATHS.reset} onClick={(event) => followLink(event, 'reset', onNavigate)}>
              Esqueci a senha
            </a>
          </div>
        )}
      </form>
    </main>
  );
}
