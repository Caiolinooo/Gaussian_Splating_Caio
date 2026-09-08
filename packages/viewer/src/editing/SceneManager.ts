import { createId } from '../ids';
import { cloneTRS, createTRS, type TRS } from '../math/trs';
import type { UnitsPort } from '../units-port';
import {
  applyOp,
  invertOp,
  labelForOp,
  type EditorCommand,
  type EditorOp,
  type SceneState,
} from './commands';
import { CommandStack } from './CommandStack';
import { applyTRSToHost, MinimalObject3D, type HostObject3D } from './hostObject';
import { listOutlinerItems, type OutlinerItem } from './outliner';
import {
  DEFAULT_CALIBRATION,
  DEFAULT_RELIGHT,
  DEFAULT_TEMPORAL,
  type BackgroundSplatJson,
  type CalibrationJson,
  type OverlayJson,
  type RelightJson,
  type SceneDocument,
  type SceneNodeJson,
  type SceneNodeKind,
  type TemporalJson,
} from './sceneSchema';
import { cloneSceneDocument, parseSceneDocument, serializeSceneDocument } from './serialize';

export interface SceneManagerOptions {
  name?: string;
  units?: UnitsPort;
  maxHistory?: number;
  createHost?: (name: string) => HostObject3D;
}

export interface AddNodeInput {
  name: string;
  kind: SceneNodeKind;
  uri: string;
  format?: SceneNodeJson['format'];
  trs?: Partial<TRS>;
  parentId?: string | null;
  visible?: boolean;
  locked?: boolean;
}

export type SceneListener = (state: SceneState) => void;

/**
 * Grafo de cena editável (splat de fundo + nós GLB/splat) com outliner,
 * TRS, undo/redo e serialização. Sem dependência de WebGL.
 */
export class SceneManager {
  readonly root: HostObject3D;
  readonly units: UnitsPort | undefined;
  private readonly stack: CommandStack<EditorCommand>;
  private readonly createHost: (name: string) => HostObject3D;
  private readonly hosts = new Map<string, HostObject3D>();
  private readonly listeners = new Set<SceneListener>();
  private state: SceneState;

  constructor(options: SceneManagerOptions = {}) {
    this.units = options.units;
    this.createHost = options.createHost ?? ((name) => new MinimalObject3D(name));
    this.stack = new CommandStack(options.maxHistory ?? 100);
    this.root = this.createHost('scene-root');
    this.state = {
      id: createId('scene'),
      name: options.name ?? 'Cena sem título',
      backgroundSplat: null,
      nodes: [],
      calibration: { ...DEFAULT_CALIBRATION },
      overlays: [],
      temporal: { ...DEFAULT_TEMPORAL },
      relight: { ...DEFAULT_RELIGHT },
    };
  }

  getState(): Readonly<SceneState> {
    return this.state;
  }

  getOutliner(): OutlinerItem[] {
    return listOutlinerItems(this.state);
  }

  getHost(id: string): HostObject3D | undefined {
    return this.hosts.get(id);
  }

  subscribe(listener: SceneListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  canUndo(): boolean {
    return this.stack.canUndo;
  }

  canRedo(): boolean {
    return this.stack.canRedo;
  }

  historyLabels(): { undo: string[]; redo: string[] } {
    return {
      undo: this.stack.undoItems.map((item) => item.label),
      redo: this.stack.redoItems.map((item) => item.label),
    };
  }

  setSceneName(name: string): void {
    this.execute({ type: 'setSceneName', name, previousName: this.state.name });
  }

  setBackground(next: BackgroundSplatJson | null): void {
    this.execute({ type: 'setBackground', previous: this.state.backgroundSplat, next });
  }

  addNode(input: AddNodeInput): SceneNodeJson {
    const node = createNodeRecord(input);
    const index = this.state.nodes.length;
    this.execute({ type: 'addNodes', nodes: [node], index });
    return node;
  }

  rename(id: string, name: string): void {
    if (this.state.backgroundSplat?.id === id) {
      this.execute({
        type: 'renameBackground',
        name,
        previousName: this.state.backgroundSplat.name,
      });
      return;
    }
    const node = this.requireNode(id);
    this.execute({ type: 'renameNode', nodeId: id, name, previousName: node.name });
  }

  setVisible(id: string, visible: boolean): void {
    if (this.state.backgroundSplat?.id === id) {
      this.execute({ type: 'setBackgroundVisible', visible });
      return;
    }
    this.requireNode(id);
    this.execute({ type: 'setVisible', target: 'node', nodeId: id, visible });
  }

  setTRS(id: string, trs: TRS): void {
    const node = this.requireNode(id);
    if (node.locked) {
      throw new Error(`Nó bloqueado: ${id}`);
    }
    this.execute({ type: 'setTRS', nodeId: id, trs: cloneTRS(trs), previous: cloneTRS(node.trs) });
  }

  duplicate(id: string): SceneNodeJson {
    const source = this.requireNode(id);
    const copy = cloneNodeWithNewId(source, `${source.name} cópia`);
    copy.trs = cloneTRS({
      ...source.trs,
      position: {
        x: source.trs.position.x + 0.1,
        y: source.trs.position.y,
        z: source.trs.position.z,
      },
    });
    this.execute({ type: 'addNodes', nodes: [copy], index: this.state.nodes.length });
    return copy;
  }

  delete(id: string): void {
    if (this.state.backgroundSplat?.id === id) {
      this.setBackground(null);
      return;
    }
    const removed = collectSubtree(this.state.nodes, id);
    if (removed.length === 0) {
      throw new Error(`Nó não encontrado: ${id}`);
    }
    const index = this.state.nodes.findIndex((node) => node.id === id);
    this.execute({
      type: 'removeNodes',
      nodeIds: removed.map((node) => node.id),
      removed,
      index: Math.max(0, index),
    });
  }

  setCalibration(next: CalibrationJson): void {
    this.execute({ type: 'setCalibration', previous: this.state.calibration, next });
  }

  setOverlays(next: OverlayJson[]): void {
    this.execute({ type: 'setOverlays', previous: this.state.overlays, next });
  }

  setTemporal(next: TemporalJson): void {
    this.state = { ...this.state, temporal: { ...next } };
    this.emit();
  }

  setRelight(next: RelightJson): void {
    this.state = { ...this.state, relight: { ...next } };
    this.emit();
  }

  undo(): void {
    const command = this.stack.undo();
    if (!command) {
      return;
    }
    this.state = applyOp(this.state, invertOp(command.op));
    this.rebuildHosts();
    this.emit();
  }

  redo(): void {
    const command = this.stack.redo();
    if (!command) {
      return;
    }
    this.state = applyOp(this.state, command.op);
    this.rebuildHosts();
    this.emit();
  }

  toDocument(): SceneDocument {
    return cloneSceneDocument({
      schemaVersion: 1,
      id: this.state.id,
      name: this.state.name,
      backgroundSplat: this.state.backgroundSplat,
      nodes: this.state.nodes,
      calibration: this.state.calibration,
      overlays: this.state.overlays,
      temporal: this.state.temporal,
      relight: this.state.relight,
    });
  }

  fromDocument(input: SceneDocument | string | unknown): SceneDocument {
    const doc =
      typeof input === 'string' || !isSceneDocument(input)
        ? parseSceneDocument(input)
        : cloneSceneDocument(input);
    this.state = {
      id: doc.id,
      name: doc.name,
      backgroundSplat: doc.backgroundSplat,
      nodes: doc.nodes,
      calibration: doc.calibration,
      overlays: doc.overlays,
      temporal: doc.temporal,
      relight: doc.relight,
    };
    this.stack.clear();
    this.rebuildHosts();
    this.emit();
    return this.toDocument();
  }

  toJSON(): string {
    return serializeSceneDocument(this.toDocument());
  }

  bindHost(id: string, host: HostObject3D): void {
    this.hosts.set(id, host);
    const node = this.state.nodes.find((item) => item.id === id);
    if (node) {
      host.name = node.name;
      host.visible = node.visible;
      applyTRSToHost(host, node.trs);
    }
  }

  private execute(op: EditorOp): void {
    const command: EditorCommand = Object.freeze({
      id: createId('cmd'),
      label: labelForOp(op),
      op: Object.freeze(op) as EditorOp,
    });
    this.state = applyOp(this.state, op);
    this.stack.push(command);
    this.rebuildHosts();
    this.emit();
  }

  private requireNode(id: string): SceneNodeJson {
    const node = this.state.nodes.find((item) => item.id === id);
    if (!node) {
      throw new Error(`Nó não encontrado: ${id}`);
    }
    return node;
  }

  private rebuildHosts(): void {
    const liveIds = new Set(this.state.nodes.map((node) => node.id));
    if (this.state.backgroundSplat) {
      liveIds.add(this.state.backgroundSplat.id);
    }

    for (const id of [...this.hosts.keys()]) {
      if (!liveIds.has(id)) {
        const host = this.hosts.get(id);
        if (host?.parent) {
          host.parent.remove(host);
        }
        this.hosts.delete(id);
      }
    }

    if (this.state.backgroundSplat) {
      this.ensureHost(this.state.backgroundSplat.id, this.state.backgroundSplat.name);
    }

    const byId = new Map(this.state.nodes.map((node) => [node.id, node]));
    for (const node of this.state.nodes) {
      const host = this.ensureHost(node.id, node.name);
      host.name = node.name;
      host.visible = node.visible;
      applyTRSToHost(host, node.trs);
      const parent =
        node.parentId && this.hosts.get(node.parentId) ? this.hosts.get(node.parentId) : this.root;
      if (host.parent !== parent && parent) {
        parent.add(host);
      }
    }

    // Pais removidos / reparent: nós cujo parentId aponta para algo inexistente vão ao root.
    for (const node of this.state.nodes) {
      if (node.parentId && !byId.has(node.parentId) && !this.isBackground(node.parentId)) {
        const host = this.hosts.get(node.id);
        if (host && host.parent !== this.root) {
          this.root.add(host);
        }
      }
    }
  }

  private isBackground(id: string): boolean {
    return this.state.backgroundSplat?.id === id;
  }

  private ensureHost(id: string, name: string): HostObject3D {
    const existing = this.hosts.get(id);
    if (existing) {
      return existing;
    }
    const host = this.createHost(name);
    this.hosts.set(id, host);
    this.root.add(host);
    return host;
  }

  private emit(): void {
    for (const listener of this.listeners) {
      listener(this.state);
    }
  }
}

function createNodeRecord(input: AddNodeInput): SceneNodeJson {
  const format = input.format ?? defaultFormat(input.kind);
  return {
    id: createId('node'),
    name: input.name,
    kind: input.kind,
    uri: input.uri,
    format,
    visible: input.visible !== false,
    locked: input.locked === true,
    trs: createTRS(input.trs),
    parentId: input.parentId ?? null,
  };
}

function defaultFormat(kind: SceneNodeKind): SceneNodeJson['format'] {
  switch (kind) {
    case 'glb':
      return 'glb';
    case 'splat':
      return 'ksplat';
    default:
      return ((_: never) => {
        throw new Error(`Kind inválido: ${String(_)}`);
      })(kind);
  }
}

function cloneNodeWithNewId(source: SceneNodeJson, name: string): SceneNodeJson {
  return {
    ...source,
    id: createId('node'),
    name,
    parentId: source.parentId,
    trs: cloneTRS(source.trs),
  };
}

function collectSubtree(nodes: SceneNodeJson[], rootId: string): SceneNodeJson[] {
  const result: SceneNodeJson[] = [];
  const visit = (id: string): void => {
    const node = nodes.find((item) => item.id === id);
    if (!node) {
      return;
    }
    result.push(node);
    for (const child of nodes) {
      if (child.parentId === id) {
        visit(child.id);
      }
    }
  };
  visit(rootId);
  return result;
}

function isSceneDocument(value: unknown): value is SceneDocument {
  return (
    typeof value === 'object' &&
    value !== null &&
    'schemaVersion' in value &&
    (value as SceneDocument).schemaVersion === 1 &&
    'nodes' in value
  );
}
