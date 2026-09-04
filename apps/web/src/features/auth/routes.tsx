import { AuthGuard, type AuthGuardProps } from './AuthGuard';
import { LoginPage, type AuthPageProps } from './LoginPage';
import { ResetPage } from './ResetPage';
import { SignupPage } from './SignupPage';

export type AuthView = 'login' | 'signup' | 'reset';

export interface AuthRouteProps extends AuthPageProps {
  page?: AuthView;
}

export function AuthRoute({ page = 'login', ...props }: AuthRouteProps) {
  switch (page) {
    case 'login':
      return <LoginPage {...props} />;
    case 'signup':
      return <SignupPage {...props} />;
    case 'reset':
      return <ResetPage {...props} />;
    default: {
      const exhaustive: never = page;
      throw new Error(`Página de auth não tratada: ${String(exhaustive)}`);
    }
  }
}

export function LoginRoute(props: AuthPageProps) {
  return <LoginPage {...props} />;
}

export function SignupRoute(props: AuthPageProps) {
  return <SignupPage {...props} />;
}

export function ResetRoute(props: AuthPageProps) {
  return <ResetPage {...props} />;
}

export function AuthGuardRoute(props: AuthGuardProps) {
  return <AuthGuard {...props} />;
}
