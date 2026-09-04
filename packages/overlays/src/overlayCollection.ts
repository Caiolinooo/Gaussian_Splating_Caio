import type { Overlay, OverlayDocument, OverlayDraft, OverlayPatch } from './types';
import { parseOverlayDocument, toOverlayDocument } from './serialize';
import { OverlayValidationError, createOverlay, mergeOverlay } from './validate';

export type OverlayCollectionListener = (overlays: readonly Overlay[]) => void;

/**
 * CRUD em memória da lista de overlays (sem three.js).
 * `OverlayManager` usa esta coleção e sincroniza a cena.
 */
export class OverlayCollection {
  private readonly items: Overlay[] = [];
  private readonly listeners = new Set<OverlayCollectionListener>();

  /**
   * Inscreve-se em mudanças da lista (substituível por um store Zustand no app).
   */
  subscribe(listener: OverlayCollectionListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Lista na ordem de render (primeiro = atrás). */
  list(): Overlay[] {
    return this.items.map((item) => ({ ...item }));
  }

  get(id: string): Overlay | undefined {
    const found = this.items.find((item) => item.id === id);
    return found ? { ...found } : undefined;
  }

  /** Cria e anexa um overlay ao final da ordem de render. */
  add(draft: OverlayDraft): Overlay {
    const overlay = createOverlay(draft);
    if (this.items.some((item) => item.id === overlay.id)) {
      throw new OverlayValidationError(`Duplicate overlay id: ${overlay.id}`);
    }
    this.items.push(overlay);
    this.emit();
    return { ...overlay };
  }

  /** Atualiza campos e revalida o modelo. */
  update(id: string, patch: OverlayPatch): Overlay {
    const index = this.indexOf(id);
    const next = mergeOverlay(this.items[index] as Overlay, patch);
    if (next.id !== id) {
      throw new OverlayValidationError('overlay id is immutable');
    }
    this.items[index] = next;
    this.emit();
    return { ...next };
  }

  /** Remove pelo id. Devolve `false` se não existir. */
  remove(id: string): boolean {
    const index = this.items.findIndex((item) => item.id === id);
    if (index < 0) {
      return false;
    }
    this.items.splice(index, 1);
    this.emit();
    return true;
  }

  /**
   * Redefine a ordem de render. `ids` deve ser uma permutação dos ids atuais.
   */
  setOrder(ids: readonly string[]): Overlay[] {
    if (ids.length !== this.items.length) {
      throw new OverlayValidationError('setOrder ids must be a permutation of current overlays');
    }
    const byId = new Map(this.items.map((item) => [item.id, item]));
    const next: Overlay[] = [];
    const seen = new Set<string>();
    for (const id of ids) {
      const item = byId.get(id);
      if (!item) {
        throw new OverlayValidationError(`Unknown overlay id in setOrder: ${id}`);
      }
      if (seen.has(id)) {
        throw new OverlayValidationError(`Duplicate overlay id in setOrder: ${id}`);
      }
      seen.add(id);
      next.push(item);
    }
    this.items.splice(0, this.items.length, ...next);
    this.emit();
    return this.list();
  }

  clear(): void {
    if (this.items.length === 0) {
      return;
    }
    this.items.splice(0, this.items.length);
    this.emit();
  }

  /** Documento versionado para o JSON de cena. */
  serialize(): OverlayDocument {
    return toOverlayDocument(this.items);
  }

  /** Substitui o estado a partir de um documento (round-trip). */
  replaceFromDocument(input: unknown): OverlayDocument {
    const doc = parseOverlayDocument(input);
    this.items.splice(0, this.items.length, ...doc.overlays);
    this.emit();
    return doc;
  }

  private indexOf(id: string): number {
    const index = this.items.findIndex((item) => item.id === id);
    if (index < 0) {
      throw new OverlayValidationError(`Overlay not found: ${id}`);
    }
    return index;
  }

  private emit(): void {
    const snapshot = this.list();
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
}
