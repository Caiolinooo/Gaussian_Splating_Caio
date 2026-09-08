import type { ExplainedError } from './types';

const KNOWN_CODES = [
  'FEW_MATCHES',
  'FEW_REGISTERED',
  'NO_RECONSTRUCTION',
  'COLMAP_FAILED',
  'TOO_FEW_FRAMES',
  'VIDEO_UNREADABLE',
  'INVALID_FORMAT',
  'TOO_SMALL',
  'EMPTY_SET',
  'HEIC_UNSUPPORTED',
  'INVALID_TRANSITION',
  'NOT_FOUND',
  'CANCELLED',
  'TRAINER_FAILED',
  'PIPELINE_ERROR',
  'UNAUTHORIZED',
  'FORBIDDEN',
  'UPLOAD_FAILED',
] as const;

type KnownErrorCode = (typeof KNOWN_CODES)[number];

function isKnownCode(code: string): code is KnownErrorCode {
  return (KNOWN_CODES as readonly string[]).includes(code);
}

const CATALOG: Record<KnownErrorCode, Omit<ExplainedError, 'code'>> = {
  FEW_MATCHES: {
    title: 'Poucas correspondências no SfM',
    message:
      'O COLMAP encontrou poucas correspondências entre as imagens — paredes lisas, trechos escuros ou movimento rápido atrapalham.',
    action:
      'Grave de novo com mais textura, luz uniforme e movimento mais lento, com bastante sobreposição.',
  },
  FEW_REGISTERED: {
    title: 'Poucas imagens registradas',
    message:
      'Menos de 70% dos frames entraram na reconstrução. A cena fica incompleta ou distorcida.',
    action: 'Filme com mais sobreposição entre os trechos e evite giros bruscos ou zoom.',
  },
  NO_RECONSTRUCTION: {
    title: 'A cena 3D não pôde ser montada',
    message: 'O COLMAP não conseguiu montar a reconstrução a partir deste material.',
    action: 'Capture o ambiente outra vez, com textura visível, sobreposição e iluminação estável.',
  },
  COLMAP_FAILED: {
    title: 'Falha na etapa COLMAP',
    message: 'A reconstrução estrutural (SfM) interrompeu com erro técnico.',
    action:
      'Baixe o registro COLMAP do job para ver a causa exata. Abra Setup e confirme que o COLMAP está instalado e executando; se o erro persistir, recapture o material com mais textura/luz.',
  },
  TOO_FEW_FRAMES: {
    title: 'Poucos frames nítidos',
    message: 'Depois de filtrar blur e duplicatas, restaram poucos frames para o SfM.',
    action: 'Grave com mais tempo, menos movimento brusco e melhor iluminação.',
  },
  VIDEO_UNREADABLE: {
    title: 'Vídeo ilegível',
    message: 'Não foi possível ler o arquivo de vídeo.',
    action: 'Confira se o arquivo não está corrompido e envie em MP4, MOV ou WEBM.',
  },
  INVALID_FORMAT: {
    title: 'Formato não suportado',
    message: 'Algum arquivo está num formato que o pipeline não aceita.',
    action: 'Envie vídeo MP4/MOV/WEBM ou imagens JPG, PNG ou HEIC.',
  },
  TOO_SMALL: {
    title: 'Resolução insuficiente',
    message: 'Uma ou mais imagens estão abaixo de 640×480 px.',
    action: 'Use fotos de celular em resolução nativa, sem recortes minúsculos.',
  },
  EMPTY_SET: {
    title: 'Nenhuma imagem válida',
    message: 'O conjunto enviado não tinha fotos utilizáveis.',
    action: 'Envie pelo menos 20 fotos nítidas do mesmo ambiente.',
  },
  HEIC_UNSUPPORTED: {
    title: 'HEIC não pôde ser aberto',
    message: 'O ambiente não conseguiu decodificar um arquivo HEIC.',
    action: 'Converta as fotos para JPG/PNG e envie de novo.',
  },
  INVALID_TRANSITION: {
    title: 'Estado do job inválido',
    message: 'O job está num estado que não permite esta operação.',
    action: 'Atualize a lista de jobs. Se o problema continuar, inicie um novo processamento.',
  },
  NOT_FOUND: {
    title: 'Job não encontrado',
    message: 'Este processamento não existe ou não pertence à sua conta.',
    action: 'Volte à lista de jobs e abra um item seu.',
  },
  CANCELLED: {
    title: 'Job cancelado',
    message: 'O processamento foi cancelado.',
    action: 'Envie o material novamente se ainda quiser a cena.',
  },
  TRAINER_FAILED: {
    title: 'Falha no treino 3DGS',
    message: 'O treinamento das gaussianas interrompeu antes de concluir.',
    action: 'Tente de novo. Se repetir, baixe o registro e fale com o suporte.',
  },
  PIPELINE_ERROR: {
    title: 'Erro no pipeline',
    message: 'Uma etapa do processamento falhou.',
    action: 'Leia a mensagem abaixo e o registro. Corrija o material ou tente novamente.',
  },
  UNAUTHORIZED: {
    title: 'Sessão expirada',
    message: 'Você precisa entrar de novo para acompanhar ou enviar jobs.',
    action: 'Entre com sua conta e tente outra vez.',
  },
  FORBIDDEN: {
    title: 'Acesso negado',
    message: 'Este job pertence a outra conta.',
    action: 'Abra apenas os processamentos da sua lista.',
  },
  UPLOAD_FAILED: {
    title: 'Falha no envio',
    message: 'Os arquivos não chegaram completos ao servidor.',
    action: 'Verifique a conexão e envie novamente. Uma nova chave de idempotência será gerada.',
  },
};

export function explainJobError(
  code: string | null | undefined,
  fallbackMessage?: string | null,
): ExplainedError {
  const normalized = (code ?? '').trim().toUpperCase();
  if (normalized && isKnownCode(normalized)) {
    const entry = CATALOG[normalized];
    return {
      code: normalized,
      title: entry.title,
      message: fallbackMessage?.trim() || entry.message,
      action: entry.action,
    };
  }
  return {
    code: normalized || 'PIPELINE_ERROR',
    title: 'Algo deu errado neste job',
    message: fallbackMessage?.trim() || CATALOG.PIPELINE_ERROR.message,
    action: CATALOG.PIPELINE_ERROR.action,
  };
}
