import {
  GIF_EXTENSIONS,
  IMAGE_EXTENSIONS,
  MAX_IMAGE_BYTES,
  MAX_IMAGES,
  MAX_IMAGES_TOTAL_BYTES,
  MAX_VIDEO_BYTES,
  MAX_VIDEO_DURATION_S,
  MIN_IMAGE_HEIGHT,
  MIN_IMAGE_WIDTH,
  MIN_IMAGES,
  MIN_VIDEO_DURATION_S,
  PLY_EXTENSIONS,
  VIDEO_EXTENSIONS,
} from './constants';
import type { SourceKind } from './types';

export type MediaKind = SourceKind | 'mixed' | 'empty' | 'unknown';

/** Superfície mínima de `File` — permite testes sem o construtor DOM. */
export interface NamedBlob {
  name: string;
  size: number;
  type: string;
}

export interface FileClassification {
  kind: MediaKind;
  videos: NamedBlob[];
  images: NamedBlob[];
  gifs: NamedBlob[];
  plys: NamedBlob[];
  others: NamedBlob[];
}

export interface SyncValidationResult {
  ok: boolean;
  kind: MediaKind;
  errors: string[];
}

function extensionOf(file: NamedBlob): string {
  const name = file.name.toLowerCase();
  const dot = name.lastIndexOf('.');
  return dot >= 0 ? name.slice(dot) : '';
}

function isVideoFile(file: NamedBlob): boolean {
  const ext = extensionOf(file);
  if ((VIDEO_EXTENSIONS as readonly string[]).includes(ext)) {
    return true;
  }
  return file.type.startsWith('video/');
}

function isGifFile(file: NamedBlob): boolean {
  const ext = extensionOf(file);
  return (GIF_EXTENSIONS as readonly string[]).includes(ext) || file.type === 'image/gif';
}

function isPlyFile(file: NamedBlob): boolean {
  const ext = extensionOf(file);
  return (PLY_EXTENSIONS as readonly string[]).includes(ext);
}

function isImageFile(file: NamedBlob): boolean {
  if (isGifFile(file)) {
    return false;
  }
  const ext = extensionOf(file);
  if ((IMAGE_EXTENSIONS as readonly string[]).includes(ext)) {
    return true;
  }
  return file.type.startsWith('image/');
}

export function classifyFiles(files: readonly NamedBlob[]): FileClassification {
  const videos: NamedBlob[] = [];
  const images: NamedBlob[] = [];
  const gifs: NamedBlob[] = [];
  const plys: NamedBlob[] = [];
  const others: NamedBlob[] = [];
  for (const file of files) {
    if (isPlyFile(file)) {
      plys.push(file);
      continue;
    }
    if (isGifFile(file)) {
      gifs.push(file);
      continue;
    }
    if (isVideoFile(file) && !isImageFile(file)) {
      videos.push(file);
      continue;
    }
    if (isImageFile(file)) {
      images.push(file);
      continue;
    }
    if (isVideoFile(file)) {
      videos.push(file);
      continue;
    }
    others.push(file);
  }
  const buckets = [videos.length > 0, images.length > 0, gifs.length > 0, plys.length > 0].filter(
    Boolean,
  ).length;
  if (files.length === 0) {
    return { kind: 'empty', videos, images, gifs, plys, others };
  }
  if (others.length > 0) {
    return { kind: 'unknown', videos, images, gifs, plys, others };
  }
  if (buckets > 1) {
    return { kind: 'mixed', videos, images, gifs, plys, others };
  }
  if (plys.length > 0) {
    return { kind: 'ply', videos, images, gifs, plys, others };
  }
  if (gifs.length > 0) {
    return { kind: 'gif', videos, images, gifs, plys, others };
  }
  if (videos.length > 0) {
    return { kind: 'video', videos, images, gifs, plys, others };
  }
  if (images.length > 0) {
    return { kind: 'images', videos, images, gifs, plys, others };
  }
  return { kind: 'unknown', videos, images, gifs, plys, others };
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KiB`;
  }
  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
  }
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GiB`;
}

export function formatClock(seconds: number): string {
  const safe = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safe / 60);
  const rest = safe % 60;
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours} h ${mins} min`;
  }
  if (minutes === 0) {
    return `${rest} s`;
  }
  return `${minutes} min ${rest.toString().padStart(2, '0')} s`;
}

function validateVideoSync(file: NamedBlob): string[] {
  const errors: string[] = [];
  const ext = extensionOf(file);
  if (!(VIDEO_EXTENSIONS as readonly string[]).includes(ext)) {
    errors.push(
      `Formato de vídeo não suportado (${ext || 'desconhecido'}). Envie MP4, MOV ou WEBM.`,
    );
  }
  if (file.size > MAX_VIDEO_BYTES) {
    errors.push(
      `O vídeo tem ${formatBytes(file.size)}. O limite é ${formatBytes(MAX_VIDEO_BYTES)}.`,
    );
  }
  if (file.size === 0) {
    errors.push('O arquivo de vídeo está vazio.');
  }
  return errors;
}

function validateImagesSync(files: readonly NamedBlob[]): string[] {
  const errors: string[] = [];
  if (files.length < MIN_IMAGES) {
    errors.push(
      `Envie pelo menos ${MIN_IMAGES} imagens (recebemos ${files.length}). O SfM precisa de bastante sobreposição.`,
    );
  }
  if (files.length > MAX_IMAGES) {
    errors.push(`No máximo ${MAX_IMAGES} imagens por job (recebemos ${files.length}).`);
  }
  let total = 0;
  for (const file of files) {
    const ext = extensionOf(file);
    if (!(IMAGE_EXTENSIONS as readonly string[]).includes(ext)) {
      errors.push(`${file.name}: formato não suportado. Envie JPG, PNG ou HEIC.`);
    }
    if (file.size > MAX_IMAGE_BYTES) {
      errors.push(
        `${file.name}: ${formatBytes(file.size)} (limite ${formatBytes(MAX_IMAGE_BYTES)}).`,
      );
    }
    if (file.size === 0) {
      errors.push(`${file.name}: arquivo vazio.`);
    }
    total += file.size;
  }
  if (total > MAX_IMAGES_TOTAL_BYTES) {
    errors.push(
      `O conjunto inteiro tem ${formatBytes(total)}. O limite é ${formatBytes(MAX_IMAGES_TOTAL_BYTES)}.`,
    );
  }
  return errors;
}

export function validateFilesSync(files: readonly NamedBlob[]): SyncValidationResult {
  const classified = classifyFiles(files);
  switch (classified.kind) {
    case 'empty':
      return {
        ok: false,
        kind: classified.kind,
        errors: ['Envie um vídeo, um GIF, um PLY ou um conjunto de imagens do ambiente.'],
      };
    case 'unknown':
      return {
        ok: false,
        kind: classified.kind,
        errors: [
          'Há arquivos com formato não reconhecido. Use vídeo MP4/MOV/WEBM, GIF, PLY ou imagens JPG/PNG/HEIC.',
        ],
      };
    case 'mixed':
      return {
        ok: false,
        kind: classified.kind,
        errors: ['Envie só um tipo de origem — vídeo, GIF, PLY ou imagens, sem misturar.'],
      };
    case 'gif':
      if (classified.gifs.length !== 1) {
        return {
          ok: false,
          kind: classified.kind,
          errors: ['Envie um único GIF por job.'],
        };
      }
      {
        const gif = classified.gifs[0]!;
        const errors: string[] = [];
        if (gif.size === 0) {
          errors.push('O GIF está vazio.');
        }
        if (gif.size > MAX_VIDEO_BYTES) {
          errors.push(
            `O GIF tem ${formatBytes(gif.size)}. O limite é ${formatBytes(MAX_VIDEO_BYTES)}.`,
          );
        }
        return { ok: errors.length === 0, kind: 'gif', errors };
      }
    case 'ply':
      if (classified.plys.length !== 1) {
        return {
          ok: false,
          kind: classified.kind,
          errors: ['Envie um único arquivo .ply por job.'],
        };
      }
      {
        const ply = classified.plys[0]!;
        const errors: string[] = [];
        if (ply.size === 0) {
          errors.push('O arquivo PLY está vazio.');
        }
        if (ply.size > MAX_VIDEO_BYTES) {
          errors.push(
            `O PLY tem ${formatBytes(ply.size)}. O limite é ${formatBytes(MAX_VIDEO_BYTES)}.`,
          );
        }
        return { ok: errors.length === 0, kind: 'ply', errors };
      }
    case 'video':
      if (classified.videos.length !== 1) {
        return {
          ok: false,
          kind: classified.kind,
          errors: ['Envie um único vídeo por job.'],
        };
      }
      {
        const errors = validateVideoSync(classified.videos[0]!);
        return { ok: errors.length === 0, kind: 'video', errors };
      }
    case 'images': {
      const errors = validateImagesSync(classified.images);
      return { ok: errors.length === 0, kind: 'images', errors };
    }
    default: {
      const exhaustive: never = classified.kind;
      throw new Error(`Classificação de mídia não tratada: ${String(exhaustive)}`);
    }
  }
}

export function validateVideoDuration(durationS: number): string[] {
  if (!Number.isFinite(durationS) || durationS <= 0) {
    return [
      'Não foi possível ler a duração do vídeo. Verifique se o arquivo não está corrompido (MP4/MOV/WEBM).',
    ];
  }
  const errors: string[] = [];
  if (durationS < MIN_VIDEO_DURATION_S) {
    errors.push(
      `O vídeo tem ${formatClock(durationS)}. Grave pelo menos ${MIN_VIDEO_DURATION_S} s com movimento lento e bastante textura.`,
    );
  }
  if (durationS > MAX_VIDEO_DURATION_S) {
    errors.push(
      `O vídeo tem ${formatClock(durationS)}. O limite é ${formatClock(MAX_VIDEO_DURATION_S)} — recorte o trecho do ambiente.`,
    );
  }
  return errors;
}

export function validateImageDimensions(width: number, height: number, fileName: string): string[] {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return [`${fileName}: não foi possível ler as dimensões.`];
  }
  if (width < MIN_IMAGE_WIDTH || height < MIN_IMAGE_HEIGHT) {
    return [
      `${fileName}: ${width}×${height} px. Use no mínimo ${MIN_IMAGE_WIDTH}×${MIN_IMAGE_HEIGHT} px.`,
    ];
  }
  return [];
}

export function isHeicFile(file: NamedBlob): boolean {
  const ext = extensionOf(file);
  return (
    ext === '.heic' || ext === '.heif' || file.type === 'image/heic' || file.type === 'image/heif'
  );
}
