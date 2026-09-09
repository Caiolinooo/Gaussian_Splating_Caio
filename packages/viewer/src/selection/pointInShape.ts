/**
 * Testes de contenção ponto-forma (screen space e 3D).
 *
 * Módulo PURO: sem `three`, sem DOM. Usado pela seleção por retângulo/laço
 * (2D, em pixels) e por esfera/box (3D, em espaço de mundo).
 */

import type { Quat, Vec3 } from '../math/vec3';

/** Ponto 2D em pixels (ou qualquer unidade de tela). */
export interface ScreenPoint {
  x: number;
  y: number;
}

/** Retângulo em pixels. Largura/altura negativas são normalizadas. */
export interface RectLike {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Esfera em espaço 3D. */
export interface SphereShape {
  center: Vec3;
  radius: number;
}

/** Box (AABB/OBB) em espaço 3D. `size` é o tamanho total por eixo. */
export interface BoxShape {
  center: Vec3;
  size: Vec3;
  /** Rotação opcional (quaternion). Sem ela, o box é um AABB. */
  rotation?: Quat;
}

/**
 * Contenção em retângulo (bordas inclusivas).
 * Aceita largura/altura negativas (retângulo arrastado "de trás para frente").
 */
export function pointInRect(px: number, py: number, rect: RectLike): boolean {
  const x0 = Math.min(rect.x, rect.x + rect.width);
  const x1 = Math.max(rect.x, rect.x + rect.width);
  const y0 = Math.min(rect.y, rect.y + rect.height);
  const y1 = Math.max(rect.y, rect.y + rect.height);
  return px >= x0 && px <= x1 && py >= y0 && py <= y1;
}

/**
 * Contenção em polígono por ray casting (regra even-odd).
 *
 * Polígonos com menos de 3 pontos (linha/ponto/vazio) não delimitam área:
 * retornam `false`. O polígono é tratado como fechado (última aresta
 * liga o último ponto ao primeiro).
 */
export function pointInPolygon(
  px: number,
  py: number,
  points: readonly ScreenPoint[],
): boolean {
  const n = points.length;
  if (n < 3) {
    return false;
  }

  let inside = false;
  // j é o vértice anterior a i (começando pelo último → fecha o polígono).
  for (let i = 0, j = n - 1; i < n; j = i, i += 1) {
    const a = points[i];
    const b = points[j];
    if (!a || !b) {
      continue;
    }
    // Aresta cruza a linha horizontal em py?
    const straddles = a.y > py !== b.y > py;
    if (!straddles) {
      continue;
    }
    // X da interseção da aresta com y = py.
    const t = (py - a.y) / (b.y - a.y);
    const intersectX = a.x + t * (b.x - a.x);
    if (px < intersectX) {
      inside = !inside;
    }
  }

  return inside;
}

/** Contenção em esfera (superfície inclusiva). */
export function pointInSphere(
  cx: number,
  cy: number,
  cz: number,
  sphere: SphereShape,
): boolean {
  const radius = sphere.radius;
  if (radius < 0) {
    return false; // raio negativo não contém nada
  }
  const dx = cx - sphere.center.x;
  const dy = cy - sphere.center.y;
  const dz = cz - sphere.center.z;
  return dx * dx + dy * dy + dz * dz <= radius * radius;
}

/**
 * Rotaciona `v` pelo conjugado de `q` (inversa, assumindo quaternion unitário).
 * Equivale a trazer o ponto do espaço de mundo para o espaço local do box.
 */
function rotateByConjugate(v: Vec3, q: Quat): Vec3 {
  // Normaliza por segurança: rotações vindas de UI nem sempre vêm unitárias.
  const lenSq = q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w;
  if (lenSq === 0) {
    return { x: v.x, y: v.y, z: v.z }; // quaternion degenerado: ignora rotação
  }
  const invLen = 1 / Math.sqrt(lenSq);
  const qx = -q.x * invLen;
  const qy = -q.y * invLen;
  const qz = -q.z * invLen;
  const qw = q.w * invLen;

  // t = 2 * (q.xyz × v); v' = v + qw * t + (q.xyz × t)
  const tx = 2 * (qy * v.z - qz * v.y);
  const ty = 2 * (qz * v.x - qx * v.z);
  const tz = 2 * (qx * v.y - qy * v.x);

  return {
    x: v.x + qw * tx + (qy * tz - qz * ty),
    y: v.y + qw * ty + (qz * tx - qx * tz),
    z: v.z + qw * tz + (qx * ty - qy * tx),
  };
}

/**
 * Tolerância para o teste de faces do box.
 *
 * Com rotação, a volta ao espaço local passa por `sqrt`/produtos e o ponto
 * que está exatamente sobre a face pode cair ~1e-16 fora dela. A tolerância
 * garante que "sobre a face" conte como dentro (comportamento esperado ao
 * selecionar splats na borda da região).
 */
const FACE_EPSILON = 1e-6;

/**
 * Contenção em box. Sem `rotation` é um AABB; com rotação é um OBB:
 * o ponto relativo ao centro é levado ao espaço local pelo quaternion inverso
 * e então testado contra o AABB local (faces inclusivas, com tolerância).
 */
export function pointInBox(
  cx: number,
  cy: number,
  cz: number,
  box: BoxShape,
): boolean {
  let lx = cx - box.center.x;
  let ly = cy - box.center.y;
  let lz = cz - box.center.z;

  const rotation = box.rotation;
  if (rotation && !(rotation.x === 0 && rotation.y === 0 && rotation.z === 0)) {
    const local = rotateByConjugate({ x: lx, y: ly, z: lz }, rotation);
    lx = local.x;
    ly = local.y;
    lz = local.z;
  }

  const hx = box.size.x * 0.5;
  const hy = box.size.y * 0.5;
  const hz = box.size.z * 0.5;

  return (
    Math.abs(lx) <= hx + FACE_EPSILON &&
    Math.abs(ly) <= hy + FACE_EPSILON &&
    Math.abs(lz) <= hz + FACE_EPSILON
  );
}
