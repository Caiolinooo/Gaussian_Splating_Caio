import type { BackendReasonCode, RendererBackendKind } from './SplatRenderer';

/** Resultado da detecção para badge de qualidade na UI. */
export type DetectedBackendKind = RendererBackendKind | 'none';

export interface GpuAdapterLike {
  requestAdapter?: (options?: unknown) => Promise<unknown>;
}

export interface DetectBackendOptions {
  /** Força um backend (útil em testes e flag de debug). */
  force?: RendererBackendKind;
  /** Injete `navigator.gpu` (ou `null`) nos testes. */
  gpu?: GpuAdapterLike | null;
  /** Injete o resultado do probe WebGL2 nos testes. */
  hasWebGL2?: boolean;
  /**
   * Se true, escolhe Spark também quando só houver WebGL2.
   * Padrão false: política do produto (Spark só com WebGPU; WebGL2 → MkKellogg).
   */
  preferSparkOnWebGL2?: boolean;
}

export interface BackendDetection {
  backend: DetectedBackendKind;
  reason: string;
  reasonCode: BackendReasonCode;
  webgpu: boolean;
  webgl2: boolean;
}

/**
 * Detecta capability (WebGPU / WebGL2) e escolhe o backend.
 * Spark é o primário quando há adapter WebGPU; MkKellogg é o fallback WebGL2.
 */
export async function detectBackend(options: DetectBackendOptions = {}): Promise<BackendDetection> {
  const webgpu = await probeWebGPU(options.gpu);
  const webgl2 = options.hasWebGL2 ?? probeWebGL2();

  if (options.force) {
    return describeForced(options.force, webgpu, webgl2);
  }

  if (webgpu) {
    return {
      backend: 'spark',
      reasonCode: 'webgpu',
      reason: 'WebGPU disponível — Spark (primário)',
      webgpu,
      webgl2,
    };
  }

  if (webgl2) {
    if (options.preferSparkOnWebGL2) {
      return {
        backend: 'spark',
        reasonCode: 'spark-webgl2',
        reason: 'WebGL2 disponível — Spark (WebGL, política alternativa)',
        webgpu,
        webgl2,
      };
    }
    return {
      backend: 'mkkellogg',
      reasonCode: 'webgl2-fallback',
      reason: 'WebGPU indisponível — fallback @mkkellogg (WebGL2)',
      webgpu,
      webgl2,
    };
  }

  return {
    backend: 'none',
    reasonCode: 'unsupported',
    reason: 'Nem WebGPU nem WebGL2 disponíveis',
    webgpu,
    webgl2,
  };
}

function describeForced(
  force: RendererBackendKind,
  webgpu: boolean,
  webgl2: boolean,
): BackendDetection {
  switch (force) {
    case 'spark':
      return {
        backend: 'spark',
        reasonCode: 'forced',
        reason: 'Backend forçado: Spark',
        webgpu,
        webgl2,
      };
    case 'mkkellogg':
      return {
        backend: 'mkkellogg',
        reasonCode: 'forced',
        reason: 'Backend forçado: @mkkellogg/gaussian-splats-3d',
        webgpu,
        webgl2,
      };
    default: {
      const exhaustive: never = force;
      throw new Error(`Backend forçado inválido: ${String(exhaustive)}`);
    }
  }
}

async function probeWebGPU(injected?: GpuAdapterLike | null): Promise<boolean> {
  const gpu =
    injected !== undefined
      ? injected
      : (globalThis as { navigator?: { gpu?: GpuAdapterLike } }).navigator?.gpu;
  if (!gpu || typeof gpu.requestAdapter !== 'function') {
    return false;
  }
  try {
    const adapter = await gpu.requestAdapter();
    return adapter != null;
  } catch {
    return false;
  }
}

function probeWebGL2(): boolean {
  if (typeof document === 'undefined') {
    return false;
  }
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2');
    return gl != null;
  } catch {
    return false;
  }
}
