import { describe, expect, it } from 'vitest';

import { MinimalObject3D } from '../src/editing/hostObject';
import { SceneManager } from '../src/editing/SceneManager';
import { createTRS } from '../src/math/trs';

describe('SceneManager (Object3D mínimo, sem WebGL)', () => {
  it('lista, renomeia, oculta, duplica e remove no outliner', () => {
    const scene = new SceneManager({
      name: 'Studio',
      createHost: (name) => new MinimalObject3D(name),
    });

    scene.setBackground({
      id: 'bg',
      name: 'Fundo',
      uri: 'scan.ksplat',
      format: 'ksplat',
      visible: true,
    });

    const chair = scene.addNode({
      name: 'Cadeira',
      kind: 'glb',
      uri: 'chair.glb',
    });

    expect(scene.getOutliner().map((item) => item.name)).toEqual(['Fundo', 'Cadeira']);
    expect(scene.getHost(chair.id)?.parent).toBe(scene.root);

    scene.rename(chair.id, 'Cadeira azul');
    scene.setVisible(chair.id, false);
    const copy = scene.duplicate(chair.id);
    expect(copy.name).toBe('Cadeira azul cópia');
    expect(copy.trs.position.x).toBeCloseTo(0.1);

    scene.delete(chair.id);
    const names = scene.getOutliner().map((item) => item.name);
    expect(names).toEqual(['Fundo', 'Cadeira azul cópia']);
    expect(scene.getHost(chair.id)).toBeUndefined();
  });

  it('aplica TRS no host e recusa nó bloqueado', () => {
    const scene = new SceneManager();
    const node = scene.addNode({
      name: 'Mesa',
      kind: 'glb',
      uri: 'table.glb',
      locked: true,
    });
    expect(() => scene.setTRS(node.id, createTRS({ position: { x: 1, y: 0, z: 0 } }))).toThrow(
      /bloqueado/,
    );

    scene.delete(node.id);
    const free = scene.addNode({ name: 'Livre', kind: 'splat', uri: 'extra.ply', format: 'ply' });
    const trs = createTRS({
      position: { x: 2, y: 3, z: 4 },
      scale: { x: 2, y: 2, z: 2 },
    });
    scene.setTRS(free.id, trs);
    const host = scene.getHost(free.id);
    expect(host?.position).toEqual({ x: 2, y: 3, z: 4 });
    expect(host?.scale).toEqual({ x: 2, y: 2, z: 2 });
  });

  it('serializa e restaura o JSON da cena (round-trip)', () => {
    const scene = new SceneManager({ name: 'Origem' });
    scene.setBackground({
      id: 'bg',
      name: 'Scan',
      uri: 'a.ksplat',
      format: 'ksplat',
      visible: true,
    });
    scene.addNode({ name: 'Vaso', kind: 'glb', uri: 'vase.glb' });
    scene.setCalibration({
      scaleFactor: 1.8,
      source: 'manual',
      confidence: 1,
    });

    const json = scene.toJSON();
    const restored = new SceneManager();
    restored.fromDocument(json);

    expect(restored.getState().name).toBe('Origem');
    expect(restored.getState().nodes).toHaveLength(1);
    expect(restored.getState().backgroundSplat?.uri).toBe('a.ksplat');
    expect(restored.getState().calibration.scaleFactor).toBe(1.8);
    expect(restored.getHost(restored.getState().nodes[0]?.id ?? '')).toBeDefined();
  });

  it('desfaz e refaz uma sequência de ≥ 20 ops', () => {
    const scene = new SceneManager({ maxHistory: 40 });
    const first = scene.addNode({ name: 'N0', kind: 'glb', uri: '0.glb' });

    for (let i = 1; i < 20; i += 1) {
      scene.addNode({ name: `N${i}`, kind: 'glb', uri: `${i}.glb` });
    }
    expect(scene.getState().nodes).toHaveLength(20);

    for (let i = 0; i < 20; i += 1) {
      scene.undo();
    }
    expect(scene.getState().nodes).toHaveLength(0);
    expect(scene.getHost(first.id)).toBeUndefined();
    expect(scene.canUndo()).toBe(false);

    for (let i = 0; i < 20; i += 1) {
      scene.redo();
    }
    expect(scene.getState().nodes).toHaveLength(20);
    expect(scene.getState().nodes[19]?.name).toBe('N19');
    expect(scene.root.children).toHaveLength(20);
  });
});
