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
  | { type: 'setSceneName'; name: string; previousName: string };

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
