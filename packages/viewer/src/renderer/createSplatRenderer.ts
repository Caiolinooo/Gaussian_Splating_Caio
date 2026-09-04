import { detectBackend, type BackendDetection, type DetectBackendOptions } from './detectBackend';
import { MkKelloggBackend } from './MkKelloggBackend';
import type { SceneParent, SplatRenderer, RendererBackendKind } from './SplatRenderer';
import { SparkBackend } from './SparkBackend';

export interface SplatRendererHost {
  /** Cena three.js hospedeira (splats + meshes GLTF). */
  scene: SceneParent;
  /**
   * Renderer three.js. Obrigatório para Spark.
   * Spark 2.1 documenta WebGLRenderer — ver sparkAdapter TODOs.
   */
  renderer?: unknown;
  camera?: unknown;
}

export interface CreateSplatRendererOptions {
  force?: RendererBackendKind;
  detect?: DetectBackendOptions;
}

export interface CreateSplatRendererResult {
  renderer: SplatRenderer;
  detection: BackendDetection;
}

/**
 * Detecta o backend e instancia a implementação do contrato `SplatRenderer`.
 */
export async function createSplatRenderer(
  host: SplatRendererHost,
  options: CreateSplatRendererOptions = {},
): Promise<CreateSplatRendererResult> {
  const detection = await detectBackend({
    ...options.detect,
    force: options.force ?? options.detect?.force,
  });

  switch (detection.backend) {
    case 'spark': {
      if (!host.renderer) {
        throw new Error('Spark selecionado, mas host.renderer não foi fornecido.');
      }
      return {
        renderer: new SparkBackend({ scene: host.scene, renderer: host.renderer }, detection),
        detection,
      };
    }
    case 'mkkellogg':
      return {
        renderer: new MkKelloggBackend({ scene: host.scene }, detection),
        detection,
      };
    case 'none':
      throw new Error(detection.reason);
    default: {
      const exhaustive: never = detection.backend;
      throw new Error(`Backend não suportado: ${String(exhaustive)}`);
    }
  }
}
