import * as THREE from 'three';

import { cloneTRS, createTRS, type TRS } from '../math/trs';
import { pickClosestSplatCenter } from '../picking/splatCenters';
import type { BackendDetection } from './detectBackend';
import {
  createSparkSplatMesh,
  getSparkModule,
  type SparkRendererLike,
  type SparkSplatMeshLike,
} from './sparkAdapter';
import {
  DEFAULT_RELIGHT_PARAMS,
  relightRgb,
  type RelightParams,
} from '../relight/shEnv';
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
  type WorldBox,
} from './SplatRenderer';

export interface SparkBackendHost {
  scene: SceneParent;
  /** Spark 2.1 documenta THREE.WebGLRenderer — ver TODO no sparkAdapter. */
  renderer: unknown;
}

interface SparkEntry {
  handle: SplatHandle;
  mesh: SparkSplatMeshLike;
  trs: TRS;
  parent: SceneParent | null;
  objectUrl?: string;
}

/**
 * Backend primário (Spark). Requer um renderer three.js no host.
 */
export class SparkBackend implements SplatRenderer {
  readonly kind = 'spark' as const;
  readonly capabilities: SplatCapabilities;

  private readonly spark: SparkRendererLike;
  private readonly entries = new Map<string, SparkEntry>();
  private readonly objectUrls: string[] = [];
  private quality: SplatQuality;
  private playing = false;
  private time = 0;
  private relight: RelightParams = { ...DEFAULT_RELIGHT_PARAMS };
  private disposed = false;

  constructor(host: SparkBackendHost, detection: BackendDetection) {
    if (!host.renderer) {
      throw new Error('SparkBackend exige host.renderer (THREE.WebGLRenderer).');
    }
    const sparkMod = getSparkModule();
    this.spark = new sparkMod.SparkRenderer({ renderer: host.renderer });
    host.scene.add(this.spark);
    this.quality = { ...DEFAULT_SPLAT_QUALITY };
    this.applyMinAlpha();
    this.capabilities = {
      backend: 'spark',
      webgpu: detection.webgpu,
      webgl2: detection.webgl2,
      maxShDegree: 3,
      supportsDynamicEdits: true,
      supportsProgressiveLoad: true,
      supportsNativeSplatRaycast: true,
      selectionReason: detection.reason,
      selectionReasonCode: detection.reasonCode === 'unsupported' ? 'webgpu' : detection.reasonCode,
    };
  }

  async load(source: SplatLoadSource, options: SplatLoadOptions = {}): Promise<SplatHandle> {
    this.assertLive();
    const quality = mergeQuality(this.quality, options.quality ?? {}, 3);
    const fileBytes = source.buffer;
    const url = fileBytes ? undefined : resolveLoadUrl(source, this.objectUrls);
    const mesh = createSparkSplatMesh(getSparkModule(), {
      url,
      fileBytes,
      format: source.format,
      maxSh: quality.shDegree,
      onProgress: options.onProgress
        ? (event) => {
            const total = event.total || 1;
            options.onProgress?.({
              loaded: event.loaded,
              total,
              ratio: event.loaded / total,
            });
          }
        : undefined,
    });
    if (mesh.initialized) {
      await mesh.initialized;
    }
    const handle = { id: cryptoId() };
    const trs = createTRS(options.trs);
    applyMeshTRS(mesh, trs);
    this.entries.set(handle.id, { handle, mesh, trs, parent: null, objectUrl: url });
    this.applyRecolor();
    return handle;
  }

  addToScene(handle: SplatHandle, parent: SceneParent): void {
    const entry = this.requireEntry(handle.id);
    if (entry.parent) {
      this.removeFromScene(handle);
    }
    parent.add(entry.mesh);
    entry.parent = parent;
  }

  removeFromScene(handle: SplatHandle): void {
    const entry = this.requireEntry(handle.id);
    if (entry.mesh.removeFromParent) {
      entry.mesh.removeFromParent();
    } else if (entry.parent?.remove) {
      entry.parent.remove(entry.mesh);
    }
    entry.parent = null;
  }

  setTRS(handle: SplatHandle, trs: TRS): void {
    const entry = this.requireEntry(handle.id);
    entry.trs = cloneTRS(trs);
    applyMeshTRS(entry.mesh, entry.trs);
  }

  getTRS(handle: SplatHandle): TRS {
    return cloneTRS(this.requireEntry(handle.id).trs);
  }

  pick(ray: Ray3, options: SplatPickOptions = {}): SplatPickHit | null {
    const raycaster = new THREE.Raycaster();
    raycaster.ray.origin.set(ray.origin.x, ray.origin.y, ray.origin.z);
    raycaster.ray.direction.set(ray.direction.x, ray.direction.y, ray.direction.z);
    let best: SplatPickHit | null = null;

    for (const entry of this.entries.values()) {
      if (entry.parent == null) {
        continue;
      }
      const intersects: THREE.Intersection[] = [];
      if (entry.mesh.raycast) {
        entry.mesh.raycast(raycaster, intersects);
      }
      const hit = intersects[0];
      if (hit && (!best || hit.distance < best.distance)) {
        best = {
          handle: entry.handle,
          distance: hit.distance,
          point: { x: hit.point.x, y: hit.point.y, z: hit.point.z },
          splatIndex: typeof hit.index === 'number' ? hit.index : undefined,
        };
      }
    }

    if (best) {
      return best;
    }

    const centers = this.collectCenters();
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
    this.quality = mergeQuality(this.quality, quality, 3);
    this.applyMinAlpha();
    for (const entry of this.entries.values()) {
      entry.mesh.maxSh = this.quality.shDegree;
      entry.mesh.updateGenerator?.();
    }
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

  setTime(normalized: number): void {
    this.time = Math.max(0, Math.min(1, normalized));
  }

  getTime(): number {
    return this.time;
  }

  setRelightEnabled(enabled: boolean): void {
    this.setRelight({ ...this.relight, enabled });
  }

  setRelight(params: RelightParams): void {
    this.relight = {
      enabled: params.enabled,
      azimuthDeg: params.azimuthDeg,
      elevationDeg: params.elevationDeg,
      intensity: params.intensity,
    };
    this.applyRecolor();
  }

  isRelightEnabled(): boolean {
    return this.relight.enabled;
  }

  getGaussianCount(handle?: SplatHandle): number {
    if (handle) {
      return this.requireEntry(handle.id).mesh.numSplats ?? 0;
    }
    let total = 0;
    for (const entry of this.entries.values()) {
      total += entry.mesh.numSplats ?? 0;
    }
    return total;
  }

  getWorldBounds(handle?: SplatHandle): WorldBox | null {
    const entry = handle ? this.entries.get(handle.id) : firstEntry(this.entries);
    if (!entry) {
      return null;
    }
    return worldBoxFromSparkMesh(entry.mesh) ?? worldBoxFromCenters(entry.mesh);
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
      entry.mesh.dispose?.();
    }
    this.entries.clear();
    this.spark.dispose?.();
    for (const url of this.objectUrls) {
      URL.revokeObjectURL(url);
    }
    this.objectUrls.length = 0;
  }

  private applyRecolor(): void {
    const rgb = relightRgb(this.relight);
    for (const entry of this.entries.values()) {
      entry.mesh.recolor?.set(rgb[0], rgb[1], rgb[2]);
    }
  }

  private applyMinAlpha(): void {
    // TODO(spark): minAlpha é corte de render (0–1), não filtro de load 0–255.
    this.spark.minAlpha = this.quality.alphaRemovalThreshold / 255;
  }

  private collectCenters() {
    const samples: {
      index: number;
      center: { x: number; y: number; z: number };
      handleId: string;
      opacity?: number;
    }[] = [];
    for (const entry of this.entries.values()) {
      if (!entry.mesh.forEachSplat) {
        continue;
      }
      entry.mesh.forEachSplat((index, center, _s, _q, opacity) => {
        samples.push({
          index,
          center: { x: center.x, y: center.y, z: center.z },
          handleId: entry.handle.id,
          opacity,
        });
      });
    }
    return samples;
  }

  private requireEntry(id: string): SparkEntry {
    const entry = this.entries.get(id);
    if (!entry) {
      throw new Error(`Splat não encontrado: ${id}`);
    }
    return entry;
  }

  private assertLive(): void {
    if (this.disposed) {
      throw new Error('SparkBackend já foi disposed.');
    }
  }
}

function firstEntry<T>(entries: Map<string, T>): T | undefined {
  return entries.values().next().value;
}

function worldBoxFromSparkMesh(mesh: SparkSplatMeshLike): WorldBox | null {
  if (!mesh.getBoundingBox) {
    return null;
  }
  try {
    const box = mesh.getBoundingBox(true);
    return applyMeshWorld(mesh, box.min, box.max);
  } catch {
    return null;
  }
}

function worldBoxFromCenters(mesh: SparkSplatMeshLike): WorldBox | null {
  if (!mesh.forEachSplat) {
    return null;
  }
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let minZ = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  let maxZ = Number.NEGATIVE_INFINITY;
  mesh.forEachSplat((_index, center) => {
    minX = Math.min(minX, center.x);
    minY = Math.min(minY, center.y);
    minZ = Math.min(minZ, center.z);
    maxX = Math.max(maxX, center.x);
    maxY = Math.max(maxY, center.y);
    maxZ = Math.max(maxZ, center.z);
  });
  if (!Number.isFinite(minX)) {
    return null;
  }
  return applyMeshWorld(mesh, { x: minX, y: minY, z: minZ }, { x: maxX, y: maxY, z: maxZ });
}

function applyMeshWorld(
  mesh: SparkSplatMeshLike,
  min: { x: number; y: number; z: number },
  max: { x: number; y: number; z: number },
): WorldBox {
  mesh.updateMatrixWorld?.(true);
  const box = new THREE.Box3(
    new THREE.Vector3(min.x, min.y, min.z),
    new THREE.Vector3(max.x, max.y, max.z),
  );
  if (mesh.matrixWorld) {
    box.applyMatrix4(new THREE.Matrix4().fromArray(Array.from(mesh.matrixWorld.elements)));
  }
  return {
    min: { x: box.min.x, y: box.min.y, z: box.min.z },
    max: { x: box.max.x, y: box.max.y, z: box.max.z },
  };
}

function applyMeshTRS(mesh: SparkSplatMeshLike, trs: TRS): void {
  mesh.position.set(trs.position.x, trs.position.y, trs.position.z);
  mesh.quaternion.set(trs.rotation.x, trs.rotation.y, trs.rotation.z, trs.rotation.w);
  mesh.scale.set(trs.scale.x, trs.scale.y, trs.scale.z);
}

function cryptoId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `splat_${Math.random().toString(36).slice(2, 12)}`;
}
