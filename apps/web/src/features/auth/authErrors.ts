const KNOWN_CODES = [
  'invalid_credentials',
  'email_not_confirmed',
  'user_already_exists',
  'email_exists',
  'weak_password',
  'over_email_send_rate_limit',
  'over_request_rate_limit',
  'user_not_found',
  'same_password',
  'signup_disabled',
] as const;

type KnownAuthCode = (typeof KNOWN_CODES)[number];

function isKnownCode(code: string): code is KnownAuthCode {
  return (KNOWN_CODES as readonly string[]).includes(code);
}

function messageForCode(code: KnownAuthCode): string {
  switch (code) {
    case 'invalid_credentials':
      return 'E-mail ou senha incorretos.';
    case 'email_not_confirmed':
      return 'Confirme seu e-mail antes de entrar.';
    case 'user_already_exists':
    case 'email_exists':
      return 'Já existe uma conta com este e-mail.';
    case 'weak_password':
      return 'A senha é muito fraca. Use pelo menos 8 caracteres.';
    case 'over_email_send_rate_limit':
    case 'over_request_rate_limit':
      return 'Muitas tentativas. Aguarde um minuto e tente de novo.';
    case 'user_not_found':
      return 'Não encontramos uma conta com este e-mail.';
    case 'same_password':
      return 'A nova senha precisa ser diferente da atual.';
    case 'signup_disabled':
      return 'O cadastro está temporariamente desativado.';
    default: {
      const exhaustive: never = code;
      throw new Error(`Código de auth não tratado: ${String(exhaustive)}`);
    }
  }
}

export function mapAuthError(
  error: { message?: string; code?: string } | null | undefined,
): string {
  if (!error) {
    return 'Não foi possível autenticar. Tente novamente.';
  }
  const code = (error.code ?? '').trim();
  if (code && isKnownCode(code)) {
    return messageForCode(code);
  }
  const message = (error.message ?? '').toLowerCase();
  if (message.includes('invalid login') || message.includes('invalid credentials')) {
    return messageForCode('invalid_credentials');
  }
  if (message.includes('already registered') || message.includes('already exists')) {
    return messageForCode('email_exists');
  }
  if (message.includes('email not confirmed')) {
    return messageForCode('email_not_confirmed');
  }
  if (message.includes('rate limit')) {
    return messageForCode('over_request_rate_limit');
  }
  if (message.includes('password')) {
    return messageForCode('weak_password');
  }
  return 'Não foi possível concluir. Tente novamente.';
}

export function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}
