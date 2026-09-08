import { describe, expect, it } from 'vitest';

import { applyOp, invertOp, type EditorOp, type SceneState } from '../src/editing/commands';
import { CommandStack } from '../src/editing/CommandStack';
import { DEFAULT_CALIBRATION, DEFAULT_RELIGHT, DEFAULT_TEMPORAL } from '../src/editing/sceneSchema';
import { createTRS } from '../src/math/trs';

function emptyState(): SceneState {
  return {
    id: 'scene-1',
    name: 'Teste',
    backgroundSplat: null,
    nodes: [],
    calibration: { ...DEFAULT_CALIBRATION },
    overlays: [],
    temporal: { ...DEFAULT_TEMPORAL },
    relight: { ...DEFAULT_RELIGHT },
  };
}

describe('CommandStack', () => {
  it('faz undo/redo de ≥ 20 operações imutáveis', () => {
    const stack = new CommandStack<EditorOp>(50);
    let state = emptyState();
    const applied: EditorOp[] = [];

    for (let i = 0; i < 24; i += 1) {
      const op: EditorOp = {
        type: 'addNodes',
        index: i,
        nodes: [
          {
            id: `n${i}`,
            name: `Nó ${i}`,
            kind: 'glb',
            uri: `asset-${i}.glb`,
            format: 'glb',
            visible: true,
            locked: false,
            trs: createTRS(),
            parentId: null,
          },
        ],
      };
      state = applyOp(state, op);
      stack.push(op);
      applied.push(op);
    }

    expect(state.nodes).toHaveLength(24);
    expect(stack.undoCount).toBe(24);
    expect(stack.canRedo).toBe(false);

    for (let i = 23; i >= 0; i -= 1) {
      const op = stack.undo();
      expect(op).toBeDefined();
      state = applyOp(state, invertOp(op as EditorOp));
      expect(state.nodes).toHaveLength(i);
    }

    expect(stack.canUndo).toBe(false);
    expect(stack.canRedo).toBe(true);

    for (let i = 0; i < 24; i += 1) {
      const op = stack.redo();
      expect(op).toEqual(applied[i]);
      state = applyOp(state, op as EditorOp);
    }

    expect(state.nodes).toHaveLength(24);
    expect(state.nodes[23]?.name).toBe('Nó 23');
  });

  it('descarta o redo ao empilhar um comando novo', () => {
    const stack = new CommandStack<string>(10);
    stack.push('a');
    stack.push('b');
    stack.undo();
    expect(stack.canRedo).toBe(true);
    stack.push('c');
    expect(stack.canRedo).toBe(false);
    expect(stack.undo()).toBe('c');
    expect(stack.undo()).toBe('a');
  });

  it('respeita o teto de histórico', () => {
    const stack = new CommandStack<number>(3);
    stack.push(1);
    stack.push(2);
    stack.push(3);
    stack.push(4);
    expect(stack.undoCount).toBe(3);
    expect(stack.undo()).toBe(4);
    expect(stack.undo()).toBe(3);
    expect(stack.undo()).toBe(2);
    expect(stack.undo()).toBeUndefined();
  });

  it('inverte rename e visibilidade de forma simétrica', () => {
    const rename: EditorOp = {
      type: 'renameNode',
      nodeId: 'a',
      name: 'Novo',
      previousName: 'Antigo',
    };
    expect(invertOp(invertOp(rename))).toEqual(rename);

    const vis: EditorOp = { type: 'setVisible', target: 'node', nodeId: 'a', visible: true };
    expect(invertOp(vis)).toEqual({
      type: 'setVisible',
      target: 'node',
      nodeId: 'a',
      visible: false,
    });
  });
});
