import type {
  AppearanceParams,
  RegionShape,
  SplatDataAccessor,
  SplatRenderer,
  SplatSelection,
} from '../renderer/SplatRenderer';
import { decimateSplats, type DecimateParams, type SplatArrays } from './decimate';

/**
 * Operações de edição sobre splats.
 *
 * O Spark 2.1 NÃO expõe delete/recolor/crop/decimate por índice — ele trabalha
 * com `SplatEdit` + `SplatEditSdf` (regiões 3D aplicadas no shader). Então este
 * editor usa duas estratégias conforme a operação:
 *
 * - **Região 3D (sphere/box/plane)** → caminho do Spark (`SplatEditSdf`):
 *   é vivo, reversível e não toca nos buffers. Usado por `hideRegion`,
 *   `recolorRegion` e `crop` (crop = hide com `invert`).
 * - **Por índice (seleção de tela, decimação)** → caminho nosso: lê os dados
 *   via `getSplatData()`, reescreve e recarrega. É o único jeito de remover
 *   floaters selecionados a laço/retângulo.
 *
 * Toda operação é registrada no `CommandStack` pelo chamador (viewer) — aqui
 * ficam só os efeitos e o snapshot para desfazer.
 */

export interface SplatEditSnapshot {
  /** Cópia completa dos buffers antes da edição (para undo). */
  readonly data: SplatArrays;
  readonly count: number;
  readonly label: string;
}

export interface SplatEditorHost {
  /** Renderer que expõe dados brutos e aplica as edições. */
  renderer: SplatRenderer;
}

export type SplatEditKind =
  | 'delete'
  | 'recolor'
  | 'opacity'
  | 'crop'
  | 'decimate'
  | 'recenter';

export interface SplatEditRecord {
  readonly kind: SplatEditKind;
  readonly label: string;
  readonly before: SplatEditSnapshot;
  readonly after: SplatEditSnapshot;
}

/**
 * Ajustes de aparência aplicados por seleção.
 * `brightness`/`saturation`/`temperature`/`opacity` são multiplicativos ou
 * aditivos conforme o canal; `color` sobrescreve (modo SET_RGB do Spark).
 */
export const DEFAULT_APPEARANCE: Required<Pick<
  AppearanceParams,
  'brightness' | 'saturation' | 'temperature' | 'opacity'
>> = Object.freeze({
  brightness: 1,
  saturation: 1,
  temperature: 0,
  opacity: 1,
});

export class SplatEditor {
  private readonly host: SplatEditorHost;
  private readonly history: SplatEditRecord[] = [];

  constructor(host: SplatEditorHost) {
    this.host = host;
  }

  get records(): readonly SplatEditRecord[] {
    return this.history;
  }

  /* ---------------------------------------------------------------- *
   * Leitura
   * ---------------------------------------------------------------- */

  /** Snapshot defensivo dos buffers (usado como estado "antes"). */
  snapshot(label: string): SplatEditSnapshot | null {
    const data = this.readData();
    if (!data) {
      return null;
    }
    return { data: cloneSplatArrays(data), count: data.opacities.length, label };
  }

  private readData(): SplatArrays | null {
    const accessor = this.currentAccessor();
    if (!accessor) {
      return null;
    }
    return {
      centers: accessor.centers,
      scales: accessor.scales,
      quaternions: accessor.quaternions,
      opacities: accessor.opacities,
      colors: accessor.colors,
    };
  }

  private currentAccessor(): SplatDataAccessor | null {
    const renderer = this.host.renderer;
    if (!renderer.getSplatData) {
      return null;
    }
    // O handle ativo é o do primeiro splat — o viewer garante um só por vez.
    return renderer.getSplatData({ id: currentHandleId(renderer) });
  }

  /* ---------------------------------------------------------------- *
   * Operações
   * ---------------------------------------------------------------- */

  /**
   * Remove os splats da seleção (limpeza de floaters).
   * Estratégia: marca opacidade 0 e recarrega — o shader descarta alpha < minAlpha.
   * Devolvo o snapshot "antes" para o chamador montar o undo.
   */
  deleteSelection(selection: SplatSelection): SplatEditSnapshot | null {
    const before = this.snapshot('Excluir splats');
    if (!before) {
      return null;
    }
    const data = cloneSplatArrays(before.data);
    for (let i = 0; i < selection.count; i += 1) {
      const index = selection.indices[i];
      if (index === undefined) {
        continue;
      }
      if (index < data.opacities.length) {
        data.opacities[index] = 0;
      }
    }
    const after = this.commit('Excluir splats', before, data);
    this.host.renderer.deleteSplats?.(selection);
    return after;
  }

  /** Ajusta brilho/saturação/temperatura/opacidade de uma seleção. */
  adjustAppearance(
    selection: SplatSelection,
    params: AppearanceParams,
  ): SplatEditSnapshot | null {
    const before = this.snapshot('Ajustar aparência');
    if (!before) {
      return null;
    }
    const data = cloneSplatArrays(before.data);
    const brightness = params.brightness ?? DEFAULT_APPEARANCE.brightness;
    const saturation = params.saturation ?? DEFAULT_APPEARANCE.saturation;
    const temperature = params.temperature ?? DEFAULT_APPEARANCE.temperature;
    const opacityScale = params.opacity ?? DEFAULT_APPEARANCE.opacity;

    for (let i = 0; i < selection.count; i += 1) {
      const index = selection.indices[i];
      if (index === undefined) {
        continue;
      }
      const c = index * 3;
      applyColorAdjust(data.colors, c, brightness, saturation, temperature);
      if (opacityScale !== 1) {
        data.opacities[index] = clamp01(at(data.opacities, index) * opacityScale);
      }
    }

    this.host.renderer.adjustAppearance?.(selection, params);
    return this.commit('Ajustar aparência', before, data);
  }

  /** Mantém só o que está dentro da região (ou fora, se `invert`). */
  cropToRegion(shape: RegionShape, invert = false): SplatEditSnapshot | null {
    const before = this.snapshot('Recortar região');
    if (!before) {
      return null;
    }
    const data = cloneSplatArrays(before.data);
    const count = data.opacities.length;
    for (let i = 0; i < count; i += 1) {
      const c = i * 3;
      const inside = isInsideRegion(
        at(data.centers, c),
        at(data.centers, c + 1),
        at(data.centers, c + 2),
        shape,
      );
      if (inside === invert) {
        data.opacities[i] = 0;
      }
    }
    this.host.renderer.cropToRegion?.({ id: currentHandleId(this.host.renderer) }, shape, invert);
    return this.commit('Recortar região', before, data);
  }

  /**
   * Decimação: merge de gaussianas similares até ~`target`.
   * Devolve a nova contagem, ou null se o backend não expõe os dados.
   */
  async decimate(params: DecimateParams): Promise<number | null> {
    const before = this.snapshot('Decimar splats');
    if (!before) {
      return null;
    }
    const result = decimateSplats(before.data, params);
    this.commit('Decimar splats', before, {
      centers: result.centers,
      scales: result.scales,
      quaternions: result.quaternions,
      opacities: result.opacities,
      colors: result.colors,
    });
    await this.host.renderer.decimateSplats?.(
      { id: currentHandleId(this.host.renderer) },
      params.target,
    );
    return result.count;
  }

  /**
   * Recentraliza os splats no centroide (útil depois de cortes assimétricos).
   * Devolve o deslocamento aplicado para o chamador reposicionar a câmera.
   */
  recenter(): { x: number; y: number; z: number } | null {
    const before = this.snapshot('Recentralizar');
    if (!before) {
      return null;
    }
    const data = cloneSplatArrays(before.data);
    const count = data.opacities.length;
    let sx = 0;
    let sy = 0;
    let sz = 0;
    let weight = 0;
    for (let i = 0; i < count; i += 1) {
      const w = at(data.opacities, i);
      const c = i * 3;
      sx += at(data.centers, c) * w;
      sy += at(data.centers, c + 1) * w;
      sz += at(data.centers, c + 2) * w;
      weight += w;
    }
    if (weight <= 0) {
      return null;
    }
    const offset = { x: sx / weight, y: sy / weight, z: sz / weight };
    for (let i = 0; i < count; i += 1) {
      const c = i * 3;
      // Leitura via `at()` porque `-=` leria `number | undefined` sob
      // `noUncheckedIndexedAccess`; o comportamento é idêntico.
      data.centers[c] = at(data.centers, c) - offset.x;
      data.centers[c + 1] = at(data.centers, c + 1) - offset.y;
      data.centers[c + 2] = at(data.centers, c + 2) - offset.z;
    }
    this.commit('Recentralizar', before, data);
    return { x: -offset.x, y: -offset.y, z: -offset.z };
  }

  /* ---------------------------------------------------------------- *
   * Histórico
   * ---------------------------------------------------------------- */

  private commit(
    label: string,
    before: SplatEditSnapshot,
    data: SplatArrays,
  ): SplatEditSnapshot {
    const after: SplatEditSnapshot = {
      data,
      count: data.opacities.length,
      label,
    };
    this.history.push({
      kind: kindFromLabel(label),
      label,
      before,
      after,
    });
    return after;
  }

  /** Restaura o estado completo de um snapshot (usado pelo undo). */
  restore(snapshot: SplatEditSnapshot): void {
    const accessor = this.currentAccessor();
    if (!accessor) {
      return;
    }
    accessor.centers.set(snapshot.data.centers.subarray(0, accessor.centers.length));
    accessor.scales.set(snapshot.data.scales.subarray(0, accessor.scales.length));
    accessor.quaternions.set(
      snapshot.data.quaternions.subarray(0, accessor.quaternions.length),
    );
    accessor.opacities.set(snapshot.data.opacities.subarray(0, accessor.opacities.length));
    accessor.colors.set(snapshot.data.colors.subarray(0, accessor.colors.length));
  }
}

/* ------------------------------------------------------------------ *
 * Helpers
 * ------------------------------------------------------------------ */

function kindFromLabel(label: string): SplatEditKind {
  if (label.startsWith('Excluir')) {
    return 'delete';
  }
  if (label.startsWith('Ajustar')) {
    return 'recolor';
  }
  if (label.startsWith('Recortar')) {
    return 'crop';
  }
  if (label.startsWith('Decimar')) {
    return 'decimate';
  }
  return 'recenter';
}

function cloneSplatArrays(source: SplatArrays): SplatArrays {
  return {
    centers: source.centers.slice(),
    scales: source.scales.slice(),
    quaternions: source.quaternions.slice(),
    opacities: source.opacities.slice(),
    colors: source.colors.slice(),
  };
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

/**
 * Leitura indexada que satisfaz `noUncheckedIndexedAccess`.
 * Os índices usados aqui vêm de loops 0..length-1 (ou de bounds check
 * explícito logo acima), então o fallback 0 nunca é atingido na prática.
 */
function at(arr: Float32Array, i: number): number {
  return arr[i] ?? 0;
}

/** Brilho (multiplicativo), saturação (luminância) e temperatura (K simplificado). */
export function applyColorAdjust(
  colors: Float32Array,
  offset: number,
  brightness: number,
  saturation: number,
  temperature: number,
): void {
  let r = at(colors, offset) * brightness;
  let g = at(colors, offset + 1) * brightness;
  let b = at(colors, offset + 2) * brightness;

  if (temperature !== 0) {
    // temperature > 0 aquece (puxa para amarelo), < 0 esfria (azul).
    r = clamp01(r + temperature * 0.1);
    b = clamp01(b - temperature * 0.1);
  }

  if (saturation !== 1) {
    const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    r = clamp01(luminance + (r - luminance) * saturation);
    g = clamp01(luminance + (g - luminance) * saturation);
    b = clamp01(luminance + (b - luminance) * saturation);
  }

  colors[offset] = clamp01(r);
  colors[offset + 1] = clamp01(g);
  colors[offset + 2] = clamp01(b);
}

export function isInsideRegion(
  x: number,
  y: number,
  z: number,
  shape: RegionShape,
): boolean {
  switch (shape.type) {
    case 'sphere': {
      const dx = x - shape.center.x;
      const dy = y - shape.center.y;
      const dz = z - shape.center.z;
      return dx * dx + dy * dy + dz * dz <= shape.radius * shape.radius;
    }
    case 'box': {
      let px = x - shape.center.x;
      let py = y - shape.center.y;
      let pz = z - shape.center.z;
      if (shape.rotation) {
        ({ x: px, y: py, z: pz } = rotateInverse(px, py, pz, shape.rotation));
      }
      return (
        Math.abs(px) <= shape.size.x / 2 &&
        Math.abs(py) <= shape.size.y / 2 &&
        Math.abs(pz) <= shape.size.z / 2
      );
    }
    case 'plane': {
      // "Dentro" = do lado para onde a normal aponta.
      const dx = x - shape.point.x;
      const dy = y - shape.point.y;
      const dz = z - shape.point.z;
      return dx * shape.normal.x + dy * shape.normal.y + dz * shape.normal.z >= 0;
    }
    default:
      return false;
  }
}

function rotateInverse(
  x: number,
  y: number,
  z: number,
  q: { x: number; y: number; z: number; w: number },
): { x: number; y: number; z: number } {
  // Conjugado do quaternion aplicado ao vetor.
  const cx = -q.x;
  const cy = -q.y;
  const cz = -q.z;
  const cw = q.w;
  // v' = q⁻¹ * v * q
  const tx = cw * x + cy * z - cz * y;
  const ty = cw * y + cz * x - cx * z;
  const tz = cw * z + cx * y - cy * x;
  const tw = -cx * x - cy * y - cz * z;
  return {
    x: tx * cw + tw * -cx + ty * -cz - tz * -cy,
    y: ty * cw + tw * -cy + tz * -cx - tx * -cz,
    z: tz * cw + tw * -cz + tx * -cy - ty * -cx,
  };
}

/**
 * Resolve o handle ativo. Hoje o viewer carrega um splat por vez; se houver
 * vários, o primeiro é o fundo. Mantido isolado para facilitar multi-splat.
 */
function currentHandleId(renderer: SplatRenderer): string {
  const candidates = internalHandles(renderer);
  return candidates[0] ?? '';
}

function internalHandles(renderer: SplatRenderer): string[] {
  // Acesso defensivo: o contrato não expõe a lista, então usamos o bounds como
  // sonda de "existe splat carregado" e deixamos o handle vazio (backend
  // resolve para o ativo). Evita acoplar a estrutura interna do Spark.
  if (renderer.getWorldBounds()) {
    return [''];
  }
  return [];
}
