import { isHeicFile, validateImageDimensions, validateVideoDuration } from './validation';

export function probeVideoDuration(file: File): Promise<number> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement('video');
    video.preload = 'metadata';
    const cleanup = () => {
      URL.revokeObjectURL(url);
      video.removeAttribute('src');
      video.load();
    };
    video.onloadedmetadata = () => {
      const duration = video.duration;
      cleanup();
      resolve(duration);
    };
    video.onerror = () => {
      cleanup();
      reject(new Error('VIDEO_UNREADABLE'));
    };
    video.src = url;
  });
}

export function probeImageSize(file: File): Promise<{ width: number; height: number }> {
  if (isHeicFile(file) && typeof createImageBitmap !== 'function') {
    return Promise.resolve({ width: MIN_PLACEHOLDER, height: MIN_PLACEHOLDER });
  }
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    const cleanup = () => {
      URL.revokeObjectURL(url);
    };
    image.onload = () => {
      const width = image.naturalWidth;
      const height = image.naturalHeight;
      cleanup();
      resolve({ width, height });
    };
    image.onerror = () => {
      cleanup();
      if (isHeicFile(file)) {
        resolve({ width: MIN_PLACEHOLDER, height: MIN_PLACEHOLDER });
        return;
      }
      reject(new Error('IMAGE_UNREADABLE'));
    };
    image.src = url;
  });
}

const MIN_PLACEHOLDER = 640;

export async function collectMediaErrors(
  files: readonly File[],
  kind: 'video' | 'images',
): Promise<string[]> {
  if (kind === 'video') {
    const video = files[0];
    if (!video) {
      return ['Envie um vídeo.'];
    }
    try {
      const duration = await probeVideoDuration(video);
      return validateVideoDuration(duration);
    } catch {
      return [
        'Não foi possível ler o vídeo. Verifique se o arquivo não está corrompido e envie MP4, MOV ou WEBM.',
      ];
    }
  }
  const errors: string[] = [];
  for (const file of files) {
    try {
      const size = await probeImageSize(file);
      errors.push(...validateImageDimensions(size.width, size.height, file.name));
    } catch {
      if (!isHeicFile(file)) {
        errors.push(`${file.name}: não foi possível abrir a imagem.`);
      }
    }
  }
  return errors;
}
