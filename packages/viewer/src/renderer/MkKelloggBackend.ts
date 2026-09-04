import { cloneTRS, createTRS, IDENTITY_TRS, type TRS } from '../math/trs';
import { pickClosestSplatCenter } from '../picking/splatCenters';
import type { BackendDetection } from './detectBackend';
import {
  createDropInViewer,
  getMkKelloggModule,
  resolveMkFormat,
  type MkDropInViewerLike,
  type MkSplatSceneLike,
} from './mkKelloggAdapter';
import {
  DEFAULT_SPLAT_QUALITY,
  mergeQuality,
  resolveLoadUrl,
  type Ray3,
  type SceneParent,
  type SplatCapabilities,
  type SplatHandle,
  type SplatLoadOptions,
  type SplatLoadSource,
  type SplatPickHit,
  type SplatPickOptions,
  type SplatQuality,
  type SplatRenderer,
} from './SplatRenderer';

export interface MkKelloggBackendHost {
  scene: SceneParent;
}

interface MkEntry {
  handle: SplatHandle;
  index: number;
  scene: MkSplatSceneLike;
  trs: TRS;
  parent: SceneParent | null;
}

/**
 * Backend fallback WebGL2 via DropInViewer embutido na THREE.Scene hospedeira.
 */
export class MkKelloggBackend implements SplatRenderer {
  readonly kind = 'mkkellogg' as const;
  readonly capabilities: SplatCapabilities;

  private readonly viewer: MkDropInViewerLike;
  private readonly host: MkKelloggBackendHost;
  private readonly entries = new Map<string, MkEntry>();
  private readonly objectUrls: string[] = [];
  private quality: SplatQuality;
  private playing = false;
  private disposed = false;
  private nextIndex = 0;
  private viewerParent: SceneParent | null = null;

  constructor(host: MkKelloggBackendHost, detection: BackendDetection) {
    this.host = host;
    this.quality = { ...DEFAULT_SPLAT_QUALITY, shDegree: 1 };
    const mod = getMkKelloggModule();
    this.viewer = createDropInViewer(mod, {
      dynamicScene: true,
      useBuiltInControls: false,
      sharedMemoryForWorkers: false,
      gpuAcceleratedSort: false,
      showLoadingUI: false,
      sphericalHarmonicsDegree: Math.min(this.quality.shDegree, 2),
    });
    this.capabilities = {
      backend: 'mkkellogg',
      webgpu: detection.webgpu,
      webgl2: detection.webgl2,
      maxShDegree: 2,
      supportsDynamicEdits: true,
      supportsProgressiveLoad: true,
      supportsNativeSplatRaycast: Boolean(this.viewer.raycaster?.intersectSplatMesh),
      selectionReason: detection.reason,
      selectionReasonCode:
        detection.reasonCode === 'unsupported' ? 'webgl2-fallback' : detection.reasonCode,
    };
  }

  async load(source: SplatLoadSource, options: SplatLoadOptions = {}): Promise<SplatHandle> {
    this.assertLive();
    this.ensureViewerInScene();
    const quality = mergeQuality(this.quality, options.quality ?? {}, 2);
    const url = resolveLoadUrl(source, this.objectUrls);
    const trs = createTRS(options.trs);
    const mod = getMkKelloggModule();
    await this.viewer.addSplatScene(url, {
      format: resolveMkFormat(mod, source.format),
      splatAlphaRemovalThreshold: quality.alphaRemovalThreshold,
      showLoadingUI: false,
      position: [trs.position.x, trs.position.y, trs.position.z],
      rotation: [trs.rotation.x, trs.rotation.y, trs.rotation.z, trs.rotation.w],
      scale: [trs.scale.x, trs.scale.y, trs.scale.z],
    });
    const index = this.nextIndex;
    this.nextIndex += 1;
    const scene = this.viewer.getSplatScene?.(index) ?? this.viewer;
    applySceneTRS(scene, trs);
    const handle = { id: cryptoId() };
    this.entries.set(handle.id, { handle, index, scene, trs, parent: null });
    if (options.onProgress) {
      options.onProgress({ loaded: 1, total: 1, ratio: 1 });
    }
    return handle;
  }

  addToScene(handle: SplatHandle, parent: SceneParent): void {
    const entry = this.requireEntry(handle.id);
    this.ensureViewerInScene();
    if (entry.scene !== this.viewer) {
      parent.add(entry.scene);
    }
    entry.parent = parent;
    entry.scene.visible = true;
  }

  removeFromScene(handle: SplatHandle): void {
    const entry = this.requireEntry(handle.id);
    // TODO(mkkellogg): não há removeSplatScene público estável — detach + hide.
    if (entry.scene.removeFromParent) {
      entry.scene.removeFromParent();
    } else if (entry.parent?.remove && entry.scene !== this.viewer) {
      entry.parent.remove(entry.scene);
    }
    entry.scene.visible = false;
    entry.parent = null;
  }

  setTRS(handle: SplatHandle, trs: TRS): void {
    const entry = this.requireEntry(handle.id);
    entry.trs = cloneTRS(trs);
    applySceneTRS(entry.scene, entry.trs);
  }

  getTRS(handle: SplatHandle): TRS {
    return cloneTRS(this.requireEntry(handle.id).trs);
  }

  pick(ray: Ray3, options: SplatPickOptions = {}): SplatPickHit | null {
    const native = this.tryNativePick();
    if (native) {
      return native;
    }
    const centers = [...this.entries.values()]
      .filter((entry) => entry.parent != null)
      .map((entry) => ({
        index: entry.index,
        handleId: entry.handle.id,
        center: entry.trs.position,
      }));
    const approx = pickClosestSplatCenter(ray, centers, options);
    if (!approx?.handleId) {
      return null;
    }
    return {
      handle: { id: approx.handleId },
      distance: approx.distance,
      point: approx.point,
      splatIndex: approx.index,
    };
  }

  setQuality(quality: Partial<SplatQuality>): void {
    this.quality = mergeQuality(this.quality, quality, 2);
    // TODO(mkkellogg): SH após load pode exigir reload da cena.
  }

  getQuality(): SplatQuality {
    return { ...this.quality };
  }

  play(): void {
    this.playing = true;
  }

  pause(): void {
    this.playing = false;
  }

  isPlaying(): boolean {
    return this.playing;
  }

  getGaussianCount(handle?: SplatHandle): number {
    if (handle) {
      this.requireEntry(handle.id);
    }
    if (typeof this.viewer.getSplatCount === 'function') {
      return this.viewer.getSplatCount();
    }
    return this.viewer.splatMesh?.getSplatCount?.() ?? 0;
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    for (const entry of this.entries.values()) {
      if (entry.parent) {
        this.removeFromScene(entry.handle);
      }
    }
    this.entries.clear();
    this.viewer.dispose?.();
    if (this.viewerParent?.remove) {
      this.viewerParent.remove(this.viewer);
    }
    this.viewerParent = null;
    for (const url of this.objectUrls) {
      URL.revokeObjectURL(url);
    }
    this.objectUrls.length = 0;
  }

  private tryNativePick(): SplatPickHit | null {
    const intersect = this.viewer.raycaster?.intersectSplatMesh;
    if (!intersect || !this.viewer.splatMesh) {
      return null;
    }
    const hits: {
      distance?: number;
      splatIndex?: number;
      origin?: { x: number; y: number; z: number };
    }[] = [];
    try {
      intersect(this.viewer.splatMesh, hits);
    } catch {
      return null;
    }
    const closest = hits[0];
    if (!closest) {
      return null;
    }
    const sceneIndex =
      typeof closest.splatIndex === 'number'
        ? this.viewer.splatMesh.getSceneIndexForSplat?.(closest.splatIndex)
        : undefined;
    const entry = [...this.entries.values()].find((item) => item.index === sceneIndex);
    if (!entry) {
      return null;
    }
    return {
      handle: entry.handle,
      distance: closest.distance ?? 0,
      point: closest.origin ?? IDENTITY_TRS.position,
      splatIndex: closest.splatIndex,
    };
  }

  private ensureViewerInScene(): void {
    if (this.viewerParent) {
      return;
    }
    this.host.scene.add(this.viewer);
    this.viewerParent = this.host.scene;
  }

  private requireEntry(id: string): MkEntry {
    const entry = this.entries.get(id);
    if (!entry) {
      throw new Error(`Splat não encontrado: ${id}`);
    }
    return entry;
  }

  private assertLive(): void {
    if (this.disposed) {
      throw new Error('MkKelloggBackend já foi disposed.');
    }
  }
}

function applySceneTRS(scene: MkSplatSceneLike, trs: TRS): void {
  scene.position.set(trs.position.x, trs.position.y, trs.position.z);
  scene.quaternion.set(trs.rotation.x, trs.rotation.y, trs.rotation.z, trs.rotation.w);
  scene.scale.set(trs.scale.x, trs.scale.y, trs.scale.z);
}

function cryptoId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `splat_${Math.random().toString(36).slice(2, 12)}`;
}
