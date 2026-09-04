import { Mesh, type Object3D, type Scene, type Texture } from 'three';

import { assertNever } from './assertNever';
import { OverlayCollection, type OverlayCollectionListener } from './overlayCollection';
import { OVERLAY_RENDER_ORDER_BASE, ProjectiveDecal } from './projection/ProjectiveDecal';
import { parseOverlayDocument } from './serialize';
import type { Overlay, OverlayDocument, OverlayDraft, OverlayPatch } from './types';
import type { UnitsPort } from './units-port';

/** Carrega o mapa a partir de `textureRef` (URL, asset id, etc.). */
export type OverlayTextureLoader = (textureRef: string) => Promise<Texture | null> | Texture | null;

export interface OverlayManagerOptions {
  units: UnitsPort;
  /** Cena three.js hospedeira (splat + proxy). Opcional até o viewer montar. */
  scene?: Scene;
  /** Raiz da malha proxy (Open3D/Poisson no MVP; SuGaR/2DGS depois). */
  proxyRoot?: Object3D;
  textureLoader?: OverlayTextureLoader;
  renderOrderBase?: number;
}

/**
 * CRUD de overlays na cena, preview por uniforms e serialização do JSON.
 *
 * Overlays são meshes da proxy com shader projetivo: depth-test contra o splat,
 * `depthWrite = false`, `renderOrder` crescente. Zustand é opcional — use
 * `subscribe` ou envolva no store do app.
 */
export class OverlayManager {
  readonly collection = new OverlayCollection();

  private readonly units: UnitsPort;
  private readonly textureLoader?: OverlayTextureLoader;
  private readonly renderOrderBase: number;
  private readonly decals = new Map<string, ProjectiveDecal>();
  private readonly loadGeneration = new Map<string, number>();

  private scene: Scene | undefined;
  private proxyRoot: Object3D | undefined;

  constructor(options: OverlayManagerOptions) {
    this.units = options.units;
    this.textureLoader = options.textureLoader;
    this.renderOrderBase = options.renderOrderBase ?? OVERLAY_RENDER_ORDER_BASE;
    this.scene = options.scene;
    this.proxyRoot = options.proxyRoot;
  }

  /**
   * Liga a cena / proxy depois do load (malha pode chegar após o JSON).
   */
  attach(scene: Scene, proxyRoot: Object3D): void {
    this.scene = scene;
    this.proxyRoot = proxyRoot;
    this.remountAll();
  }

  /** Troca só a raiz da proxy e remonta os decals. */
  setProxyRoot(proxyRoot: Object3D): void {
    this.proxyRoot = proxyRoot;
    this.remountAll();
  }

  /** Cena hospedeira (splat + proxy), se já ligada. */
  get hostScene(): Scene | undefined {
    return this.scene;
  }

  subscribe(listener: OverlayCollectionListener): () => void {
    return this.collection.subscribe(listener);
  }

  list(): Overlay[] {
    return this.collection.list();
  }

  get(id: string): Overlay | undefined {
    return this.collection.get(id);
  }

  /** Cria o overlay, monta na proxy e dispara o load da textura. */
  add(draft: OverlayDraft): Overlay {
    const overlay = this.collection.add(draft);
    this.mount(overlay);
    void this.loadTexture(overlay);
    return overlay;
  }

  /**
   * Atualiza o modelo. Rebuild só se `targetSurface` ou `kind` mudarem;
   * o resto é preview (uniforms).
   */
  update(id: string, patch: OverlayPatch): Overlay {
    const previous = this.collection.get(id);
    const next = this.collection.update(id, patch);
    const rebuild =
      previous !== undefined &&
      (previous.targetSurface !== next.targetSurface || previous.kind !== next.kind);
    if (rebuild) {
      this.unmount(id);
      this.mount(next);
    } else {
      this.preview(id, {});
    }
    if (patch.textureRef !== undefined && patch.textureRef !== previous?.textureRef) {
      void this.loadTexture(next);
    }
    return next;
  }

  /**
   * Preview em tempo real: aplica o patch ao modelo e só atualiza uniforms
   * (sem nova geometria / DecalGeometry).
   */
  preview(id: string, patch: OverlayPatch): Overlay {
    const overlay =
      Object.keys(patch).length > 0 ? this.collection.update(id, patch) : this.require(id);
    const decal = this.decals.get(id);
    decal?.applyOverlay(overlay, this.units);
    return overlay;
  }

  remove(id: string): boolean {
    const removed = this.collection.remove(id);
    if (removed) {
      this.unmount(id);
    }
    return removed;
  }

  /** Reordena a composição (renderOrder = base + índice). */
  setOrder(ids: readonly string[]): Overlay[] {
    const ordered = this.collection.setOrder(ids);
    this.syncRenderOrder();
    return ordered;
  }

  /** Documento versionado para persistir no JSON de cena. */
  serialize(): OverlayDocument {
    return this.collection.serialize();
  }

  /**
   * Restaura overlays a partir do JSON de cena (round-trip com `serialize`).
   */
  loadDocument(input: unknown): OverlayDocument {
    this.disposeDecals();
    const doc = this.collection.replaceFromDocument(input);
    for (const overlay of doc.overlays) {
      this.mount(overlay);
      void this.loadTexture(overlay);
    }
    return doc;
  }

  /** Parse puro do JSON de cena (sem montar na GPU). */
  static parse(input: unknown): OverlayDocument {
    return parseOverlayDocument(input);
  }

  dispose(): void {
    this.disposeDecals();
    this.collection.clear();
  }

  private require(id: string): Overlay {
    const overlay = this.collection.get(id);
    if (!overlay) {
      throw new Error(`Overlay not found: ${id}`);
    }
    return overlay;
  }

  private mount(overlay: Overlay): void {
    if (!this.proxyRoot) {
      return;
    }
    const targets = collectTargetMeshes(this.proxyRoot, overlay.targetSurface);
    const index = this.collection.list().findIndex((item) => item.id === overlay.id);
    const decal = new ProjectiveDecal({
      overlay,
      units: this.units,
      targets,
      renderOrder: this.renderOrderBase + Math.max(index, 0),
    });
    this.decals.set(overlay.id, decal);
  }

  private unmount(id: string): void {
    const decal = this.decals.get(id);
    if (!decal) {
      return;
    }
    decal.dispose();
    this.decals.delete(id);
    this.loadGeneration.delete(id);
  }

  private remountAll(): void {
    this.disposeDecals();
    for (const overlay of this.collection.list()) {
      this.mount(overlay);
      void this.loadTexture(overlay);
    }
  }

  private syncRenderOrder(): void {
    const overlays = this.collection.list();
    overlays.forEach((overlay, index) => {
      this.decals.get(overlay.id)?.setRenderOrder(this.renderOrderBase + index);
    });
  }

  private disposeDecals(): void {
    for (const decal of this.decals.values()) {
      decal.dispose();
    }
    this.decals.clear();
    this.loadGeneration.clear();
  }

  private async loadTexture(overlay: Overlay): Promise<void> {
    const ref = textureRefOf(overlay);
    if (!ref || !this.textureLoader) {
      return;
    }
    const generation = (this.loadGeneration.get(overlay.id) ?? 0) + 1;
    this.loadGeneration.set(overlay.id, generation);
    const result = await this.textureLoader(ref);
    if (this.loadGeneration.get(overlay.id) !== generation) {
      return;
    }
    const current = this.collection.get(overlay.id);
    if (!current) {
      return;
    }
    this.decals.get(overlay.id)?.setTexture(result);
    this.decals.get(overlay.id)?.applyOverlay(current, this.units);
  }
}

function textureRefOf(overlay: Overlay): string | undefined {
  switch (overlay.kind) {
    case 'paint':
      return overlay.textureRef;
    case 'wallpaper':
    case 'sticker':
      return overlay.textureRef;
    default:
      return assertNever(overlay);
  }
}

/**
 * Resolve as malhas da proxy. `targetSurface` casa `name` ou `userData.id`.
 */
export function collectTargetMeshes(root: Object3D, targetSurface?: string): Mesh[] {
  const meshes: Mesh[] = [];
  root.traverse((node) => {
    if (!(node instanceof Mesh)) {
      return;
    }
    if (node.userData['gsOverlayWrapper'] === true) {
      return;
    }
    if (!targetSurface) {
      meshes.push(node);
      return;
    }
    const dataId = node.userData['id'];
    if (node.name === targetSurface || dataId === targetSurface) {
      meshes.push(node);
    }
  });
  return meshes;
}
