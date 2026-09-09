import { assertNever } from '../assertNever';
import { cloneTRS, type TRS } from '../math/trs';
import type {
  BackgroundSplatJson,
  CalibrationJson,
  OverlayJson,
  RelightJson,
  SceneNodeJson,
  TemporalJson,
} from './sceneSchema';

export interface SceneState {
  id: string;
  name: string;
  backgroundSplat: BackgroundSplatJson | null;
  nodes: SceneNodeJson[];
  calibration: CalibrationJson;
  overlays: OverlayJson[];
  temporal: TemporalJson;
  relight: RelightJson;
}

export type EditorOp =
  | { type: 'addNodes'; nodes: SceneNodeJson[]; index: number }
  | { type: 'removeNodes'; nodeIds: string[]; removed: SceneNodeJson[]; index: number }
  | { type: 'renameNode'; nodeId: string; name: string; previousName: string }
  | { type: 'renameBackground'; name: string; previousName: string }
  | { type: 'setVisible'; target: 'node'; nodeId: string; visible: boolean }
  | { type: 'setBackgroundVisible'; visible: boolean }
  | { type: 'setTRS'; nodeId: string; trs: TRS; previous: TRS }
  | {
      type: 'setBackground';
      previous: BackgroundSplatJson | null;
      next: BackgroundSplatJson | null;
    }
  | { type: 'setCalibration'; previous: CalibrationJson; next: CalibrationJson }
  | { type: 'setOverlays'; previous: OverlayJson[]; next: OverlayJson[] }
  | { type: 'setSceneName'; name: string; previousName: string }
  /* --- Edição de splats (C1) --- */
  | {
      type: 'splatDelete';
      /** Índices removidos (para restauração exata). */
      indices: number[];
      /** Dados completos antes da remoção. */
      previous: SplatBuffersJson | null;
      count: number;
    }
  | {
      type: 'splatAppearance';
      indices: number[];
      previous: SplatBuffersJson | null;
      next: SplatBuffersJson | null;
      params: AppearanceParams;
    }
  | {
      type: 'splatCrop';
      shape: RegionShapeJson;
      invert: boolean;
      previous: SplatBuffersJson | null;
    }
  | {
      type: 'splatDecimate';
      target: number;
      previous: SplatBuffersJson | null;
      next: SplatBuffersJson | null;
    }
  | {
      type: 'splatRecenter';
      offset: [number, number, number];
      previous: SplatBuffersJson | null;
    }
  /**
   * Restaura buffers inteiros — é o inverso de qualquer op de splat.
   * Existe separado porque o undo de splat não é uma transformação incremental:
   * o mais seguro é repor o estado anterior completo.
   */
  | { type: 'splatRestore'; buffers: SplatBuffersJson | null; label: string };

/**
 * Buffers serializáveis de um splat, para undo/redo.
 * Arrays viram `number[]` no JSON — o chamador converte de/para Float32Array.
 */
export interface SplatBuffersJson {
  centers: number[];
  scales: number[];
  quaternions: number[];
  opacities: number[];
  colors: number[];
}

/** Região 3D serializável (espelha `RegionShape` sem tipos de runtime). */
export type RegionShapeJson =
  | { type: 'sphere'; center: [number, number, number]; radius: number }
  | {
      type: 'box';
      center: [number, number, number];
      size: [number, number, number];
      rotation?: [number, number, number, number];
    }
  | { type: 'plane'; point: [number, number, number]; normal: [number, number, number] };

/** Parâmetros de aparência serializáveis. */
export interface AppearanceParams {
  brightness?: number;
  saturation?: number;
  temperature?: number;
  opacity?: number;
  color?: [number, number, number];
}

export interface EditorCommand {
  readonly id: string;
  readonly label: string;
  readonly op: EditorOp;
}

/** Inverte um comando imutável (para undo). */
export function invertOp(op: EditorOp): EditorOp {
  switch (op.type) {
    case 'addNodes':
      return {
        type: 'removeNodes',
        nodeIds: op.nodes.map((node) => node.id),
        removed: op.nodes,
        index: op.index,
      };
    case 'removeNodes':
      return { type: 'addNodes', nodes: op.removed, index: op.index };
    case 'renameNode':
      return {
        type: 'renameNode',
        nodeId: op.nodeId,
        name: op.previousName,
        previousName: op.name,
      };
    case 'renameBackground':
      return { type: 'renameBackground', name: op.previousName, previousName: op.name };
    case 'setVisible':
      return { type: 'setVisible', target: 'node', nodeId: op.nodeId, visible: !op.visible };
    case 'setBackgroundVisible':
      return { type: 'setBackgroundVisible', visible: !op.visible };
    case 'setTRS':
      return { type: 'setTRS', nodeId: op.nodeId, trs: op.previous, previous: op.trs };
    case 'setBackground':
      return { type: 'setBackground', previous: op.next, next: op.previous };
    case 'setCalibration':
      return { type: 'setCalibration', previous: op.next, next: op.previous };
    case 'setOverlays':
      return { type: 'setOverlays', previous: op.next, next: op.previous };
    case 'setSceneName':
      return { type: 'setSceneName', name: op.previousName, previousName: op.name };
    case 'splatDelete':
    case 'splatCrop':
    case 'splatDecimate':
    case 'splatRecenter':
      // Undo de splat = repor os buffers inteiros do estado anterior.
      return {
        type: 'splatRestore',
        buffers: op.previous,
        label: `Desfazer ${labelForOp(op)}`,
      };
    case 'splatAppearance':
      return {
        type: 'splatRestore',
        buffers: op.previous,
        label: 'Desfazer ajuste de aparência',
      };
    case 'splatRestore':
      // Restaurar é o inverso de si mesmo no nível do SceneState: os buffers
      // reais são reaplicados pelo viewer, que guarda o par before/after.
      return op;
    default:
      return assertNever(op);
  }
}

/** Aplica um op imutável e devolve um novo estado (clone estrutural, sem mutate). */
export function applyOp(state: SceneState, op: EditorOp): SceneState {
  const draft = cloneState(state);
  switch (op.type) {
    case 'addNodes': {
      draft.nodes.splice(op.index, 0, ...op.nodes.map(cloneNode));
      return draft;
    }
    case 'removeNodes': {
      const ids = new Set(op.nodeIds);
      draft.nodes = draft.nodes.filter((node) => !ids.has(node.id));
      return draft;
    }
    case 'renameNode': {
      const node = draft.nodes.find((item) => item.id === op.nodeId);
      if (node) {
        node.name = op.name;
      }
      return draft;
    }
    case 'renameBackground': {
      if (draft.backgroundSplat) {
        draft.backgroundSplat.name = op.name;
      }
      return draft;
    }
    case 'setVisible': {
      const node = draft.nodes.find((item) => item.id === op.nodeId);
      if (node) {
        node.visible = op.visible;
      }
      return draft;
    }
    case 'setBackgroundVisible': {
      if (draft.backgroundSplat) {
        draft.backgroundSplat.visible = op.visible;
      }
      return draft;
    }
    case 'setTRS': {
      const node = draft.nodes.find((item) => item.id === op.nodeId);
      if (node) {
        node.trs = cloneTRS(op.trs);
      }
      return draft;
    }
    case 'setBackground': {
      draft.backgroundSplat = op.next ? structuredClone(op.next) : null;
      return draft;
    }
    case 'setCalibration': {
      draft.calibration = structuredClone(op.next);
      return draft;
    }
    case 'setOverlays': {
      draft.overlays = structuredClone(op.next);
      return draft;
    }
    case 'setSceneName': {
      draft.name = op.name;
      return draft;
    }
    case 'splatDelete':
    case 'splatAppearance':
    case 'splatCrop':
    case 'splatDecimate':
    case 'splatRecenter':
    case 'splatRestore': {
      // Edição de splats não altera o grafo de cena serializado (nós, overlays,
      // calibração). O efeito acontece nos buffers do renderer, aplicado pelo
      // viewer; aqui marcamos apenas a passagem pelo histórico.
      return draft;
    }
    default:
      return assertNever(op);
  }
}

export function labelForOp(op: EditorOp): string {
  switch (op.type) {
    case 'addNodes':
      return op.nodes.length > 1 ? 'Adicionar objetos' : 'Adicionar objeto';
    case 'removeNodes':
      return op.nodeIds.length > 1 ? 'Remover objetos' : 'Remover objeto';
    case 'renameNode':
    case 'renameBackground':
      return 'Renomear';
    case 'setVisible':
    case 'setBackgroundVisible':
      return 'Alterar visibilidade';
    case 'setTRS':
      return 'Transformar';
    case 'setBackground':
      return 'Definir splat de fundo';
    case 'setCalibration':
      return 'Atualizar calibração';
    case 'setOverlays':
      return 'Atualizar overlays';
    case 'setSceneName':
      return 'Renomear cena';
    case 'splatDelete':
      return 'Excluir splats';
    case 'splatAppearance':
      return 'Ajustar aparência dos splats';
    case 'splatCrop':
      return 'Recortar splats';
    case 'splatDecimate':
      return 'Decimar splats';
    case 'splatRecenter':
      return 'Recentralizar splats';
    case 'splatRestore':
      return op.label;
    default:
      return assertNever(op);
  }
}

function cloneState(state: SceneState): SceneState {
  return {
    id: state.id,
    name: state.name,
    backgroundSplat: state.backgroundSplat ? structuredClone(state.backgroundSplat) : null,
    nodes: state.nodes.map(cloneNode),
    calibration: structuredClone(state.calibration),
    overlays: state.overlays.map((overlay) => structuredClone(overlay)),
    temporal: structuredClone(state.temporal),
    relight: structuredClone(state.relight),
  };
}

function cloneNode(node: SceneNodeJson): SceneNodeJson {
  return {
    ...node,
    trs: cloneTRS(node.trs),
  };
}
