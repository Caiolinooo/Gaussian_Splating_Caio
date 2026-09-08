const APP_NAME = 'Gaussian Splatting';

export function titleForPath(pathname: string): string {
  const path = pathname.replace(/\/+$/, '') || '/';
  if (path === '/login') {
    return `${APP_NAME} — Entrar`;
  }
  if (path === '/signup') {
    return `${APP_NAME} — Criar conta`;
  }
  if (path === '/reset') {
    return `${APP_NAME} — Redefinir senha`;
  }
  if (path === '/setup') {
    return `${APP_NAME} — Configuração do ambiente`;
  }
  if (path === '/jobs') {
    return `${APP_NAME} — Jobs`;
  }
  if (path.startsWith('/jobs/')) {
    return `${APP_NAME} — Acompanhamento do job`;
  }
  if (path === '/upload') {
    return `${APP_NAME} — Novo upload`;
  }
  if (path === '/viewer' || path.startsWith('/viewer/')) {
    return `${APP_NAME} — Viewer`;
  }
  if (path === '/editing') {
    return `${APP_NAME} — Edição`;
  }
  if (path === '/calibration') {
    return `${APP_NAME} — Calibração`;
  }
  if (path === '/overlays') {
    return `${APP_NAME} — Overlays`;
  }
  return APP_NAME;
}
