import type { SceneState } from './commands';
import type { SceneNodeKind } from './sceneSchema';

export type OutlinerKind = 'background-splat' | SceneNodeKind;

export interface OutlinerItem {
  id: string;
  name: string;
  kind: OutlinerKind;
  visible: boolean;
  locked: boolean;
  parentId: string | null;
  depth: number;
}

/** Lista o outliner: splat de fundo primeiro, depois nós em ordem de árvore. */
export function listOutlinerItems(state: SceneState): OutlinerItem[] {
  const items: OutlinerItem[] = [];
  if (state.backgroundSplat) {
    items.push({
      id: state.backgroundSplat.id,
      name: state.backgroundSplat.name,
      kind: 'background-splat',
      visible: state.backgroundSplat.visible,
      locked: true,
      parentId: null,
      depth: 0,
    });
  }

  const byParent = new Map<string | null, typeof state.nodes>();
  for (const node of state.nodes) {
    const list = byParent.get(node.parentId) ?? [];
    list.push(node);
    byParent.set(node.parentId, list);
  }

  const visit = (parentId: string | null, depth: number): void => {
    const children = byParent.get(parentId) ?? [];
    for (const child of children) {
      items.push({
        id: child.id,
        name: child.name,
        kind: child.kind,
        visible: child.visible,
        locked: child.locked,
        parentId: child.parentId,
        depth,
      });
      visit(child.id, depth + 1);
    }
  };

  visit(null, 0);
  return items;
}
