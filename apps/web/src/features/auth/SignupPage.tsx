import { useState, type FormEvent, type MouseEvent } from 'react';

import { AUTH_PATHS, useAuthStore } from './authStore';
import type { AuthPageProps } from './LoginPage';
import './auth.css';

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

export function SignupPage({ onAuthenticated, onNavigate }: AuthPageProps) {
  const { signUp, signInWithGoogle, loading, error, info, clearMessages } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const ok = await signUp(email, password);
    if (ok && useAuthStore.getState().session) {
      onAuthenticated?.();
    }
  }

  return (
    <main className="auth-screen">
      <h1>Criar conta</h1>
      <p className="muted">Cadastro com e-mail e senha. Você também pode entrar com o Google.</p>
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
          <label htmlFor="auth-signup-email">E-mail</label>
          <input
            id="auth-signup-email"
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
        <div className="auth-field">
          <label htmlFor="auth-signup-password">Senha (mínimo 8 caracteres)</label>
          <input
            id="auth-signup-password"
            type="password"
            autoComplete="new-password"
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
            {loading ? 'Criando conta…' : 'Criar conta'}
          </button>
          <div className="auth-divider">ou</div>
          <button type="button" disabled={loading} onClick={() => void signInWithGoogle()}>
            Continuar com Google
          </button>
        </div>
        <div className="auth-links">
          <a href={AUTH_PATHS.login} onClick={(event) => followLink(event, 'login', onNavigate)}>
            Já tenho conta
          </a>
        </div>
      </form>
    </main>
  );
}
