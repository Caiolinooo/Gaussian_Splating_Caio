import { describe, expect, it } from 'vitest';

import { detectBackend } from '../src/renderer/detectBackend';

describe('detectBackend', () => {
  it('escolhe Spark quando navigator.gpu devolve adapter', async () => {
    const detection = await detectBackend({
      gpu: {
        requestAdapter: async () => ({ name: 'fake-adapter' }),
      },
      hasWebGL2: true,
    });
    expect(detection.backend).toBe('spark');
    expect(detection.reasonCode).toBe('webgpu');
    expect(detection.webgpu).toBe(true);
    expect(detection.reason).toMatch(/Spark/i);
  });

  it('cai no MkKellogg quando não há WebGPU mas há WebGL2', async () => {
    const detection = await detectBackend({
      gpu: null,
      hasWebGL2: true,
    });
    expect(detection.backend).toBe('mkkellogg');
    expect(detection.reasonCode).toBe('webgl2-fallback');
    expect(detection.webgl2).toBe(true);
    expect(detection.webgpu).toBe(false);
  });

  it('retorna none quando não há WebGPU nem WebGL2', async () => {
    const detection = await detectBackend({
      gpu: { requestAdapter: async () => null },
      hasWebGL2: false,
    });
    expect(detection.backend).toBe('none');
    expect(detection.reasonCode).toBe('unsupported');
  });

  it('honra force=mkkellogg mesmo com WebGPU', async () => {
    const detection = await detectBackend({
      force: 'mkkellogg',
      gpu: { requestAdapter: async () => ({}) },
      hasWebGL2: true,
    });
    expect(detection.backend).toBe('mkkellogg');
    expect(detection.reasonCode).toBe('forced');
  });

  it('pode preferir Spark em WebGL2 via flag', async () => {
    const detection = await detectBackend({
      gpu: null,
      hasWebGL2: true,
      preferSparkOnWebGL2: true,
    });
    expect(detection.backend).toBe('spark');
    expect(detection.reasonCode).toBe('spark-webgl2');
  });

  it('trata requestAdapter que lança como WebGPU indisponível', async () => {
    const detection = await detectBackend({
      gpu: {
        requestAdapter: async () => {
          throw new Error('denied');
        },
      },
      hasWebGL2: true,
    });
    expect(detection.backend).toBe('mkkellogg');
    expect(detection.webgpu).toBe(false);
  });
});
