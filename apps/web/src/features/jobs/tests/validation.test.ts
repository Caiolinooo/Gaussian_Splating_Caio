import { describe, expect, it } from 'vitest';

import { MAX_IMAGE_BYTES, MAX_VIDEO_BYTES, MIN_IMAGES, MIN_VIDEO_DURATION_S } from '../constants';
import {
  classifyFiles,
  formatBytes,
  validateFilesSync,
  validateImageDimensions,
  validateVideoDuration,
} from '../validation';

function file(name: string, size = 1024, type = ''): { name: string; size: number; type: string } {
  return { name, size, type };
}

describe('classifyFiles', () => {
  it('reconhece um vídeo mp4', () => {
    const result = classifyFiles([file('walk.mp4', 2048, 'video/mp4')]);
    expect(result.kind).toBe('video');
    expect(result.videos).toHaveLength(1);
  });

  it('reconhece um GIF', () => {
    const result = classifyFiles([file('loop.gif', 2048, 'image/gif')]);
    expect(result.kind).toBe('gif');
    expect(result.gifs).toHaveLength(1);
  });

  it('reconhece um PLY', () => {
    const result = classifyFiles([file('scan.ply', 4096)]);
    expect(result.kind).toBe('ply');
    expect(result.plys).toHaveLength(1);
  });

  it('reconhece um conjunto de imagens', () => {
    const result = classifyFiles([file('a.jpg'), file('b.png'), file('c.heic')]);
    expect(result.kind).toBe('images');
    expect(result.images).toHaveLength(3);
  });

  it('rejeita mistura de vídeo e imagens', () => {
    const result = classifyFiles([file('a.mp4'), file('b.jpg')]);
    expect(result.kind).toBe('mixed');
  });

  it('marca vazio', () => {
    expect(classifyFiles([]).kind).toBe('empty');
  });
});

describe('validateFilesSync', () => {
  it('pede arquivo quando não há seleção', () => {
    const result = validateFilesSync([]);
    expect(result.ok).toBe(false);
    expect(result.errors[0]).toMatch(/vídeo.*GIF.*PLY|conjunto de imagens/i);
  });

  it('rejeita vídeo acima do limite', () => {
    const result = validateFilesSync([file('huge.mp4', MAX_VIDEO_BYTES + 1, 'video/mp4')]);
    expect(result.ok).toBe(false);
    expect(result.errors.some((line) => line.includes('limite'))).toBe(true);
  });

  it('rejeita poucas imagens', () => {
    const files = Array.from({ length: MIN_IMAGES - 1 }, (_, i) => file(`p${i}.jpg`));
    const result = validateFilesSync(files);
    expect(result.ok).toBe(false);
    expect(result.errors[0]).toMatch(/pelo menos/);
  });

  it('aceita um gif e um ply', () => {
    expect(validateFilesSync([file('loop.gif', 2048, 'image/gif')]).kind).toBe('gif');
    expect(validateFilesSync([file('scan.ply', 4096)]).ok).toBe(true);
  });

  it('aceita 20 jpg pequenos', () => {
    const files = Array.from({ length: MIN_IMAGES }, (_, i) =>
      file(`p${i}.jpg`, 2048, 'image/jpeg'),
    );
    const result = validateFilesSync(files);
    expect(result.ok).toBe(true);
    expect(result.kind).toBe('images');
  });

  it('rejeita imagem acima do limite individual', () => {
    const files = Array.from({ length: MIN_IMAGES }, (_, i) =>
      file(`p${i}.jpg`, i === 0 ? MAX_IMAGE_BYTES + 10 : 2048),
    );
    const result = validateFilesSync(files);
    expect(result.ok).toBe(false);
  });
});

describe('validateVideoDuration', () => {
  it('rejeita vídeo curto demais', () => {
    const errors = validateVideoDuration(MIN_VIDEO_DURATION_S - 1);
    expect(errors.length).toBeGreaterThan(0);
  });

  it('aceita 45 segundos', () => {
    expect(validateVideoDuration(45)).toEqual([]);
  });

  it('rejeita duração ilegível', () => {
    expect(validateVideoDuration(Number.NaN)[0]).toMatch(/duração/);
  });
});

describe('validateImageDimensions', () => {
  it('rejeita abaixo de 640×480', () => {
    const errors = validateImageDimensions(320, 240, 'tiny.jpg');
    expect(errors[0]).toMatch(/tiny.jpg/);
  });

  it('aceita 1920×1080', () => {
    expect(validateImageDimensions(1920, 1080, 'ok.jpg')).toEqual([]);
  });
});

describe('formatBytes', () => {
  it('formata MiB', () => {
    expect(formatBytes(2 * 1024 * 1024)).toBe('2.0 MiB');
  });
});
