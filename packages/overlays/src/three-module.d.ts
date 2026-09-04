/**
 * Declaração mínima de `three` para o typecheck deste pacote.
 * three@0.180.0 instalado no workspace não publica `.d.ts` no export ".";
 * quando o monorepo passar a resolver tipos oficiais, este arquivo pode sair.
 */
declare module 'three' {
  export class Vector2 {
    constructor(x?: number, y?: number);
    x: number;
    y: number;
    set(x: number, y: number): this;
  }

  export class Vector3 {
    constructor(x?: number, y?: number, z?: number);
    x: number;
    y: number;
    z: number;
    set(x: number, y: number, z: number): this;
    copy(v: Vector3): this;
    addScaledVector(v: Vector3, s: number): this;
    applyEuler(e: Euler): this;
  }

  export class Euler {
    constructor(x?: number, y?: number, z?: number, order?: string);
    x: number;
    y: number;
    z: number;
    set(x: number, y: number, z: number, order?: string): this;
    copy(e: Euler): this;
  }

  export class Matrix4 {
    multiplyMatrices(a: Matrix4, b: Matrix4): this;
    copy(m: Matrix4): this;
    identity(): this;
  }

  export class Color {
    constructor(r?: number, g?: number, b?: number);
    set(value: string | number | Color): this;
    copy(c: Color): this;
  }

  export class Texture {
    wrapS: Wrapping;
    wrapT: Wrapping;
    colorSpace: string;
    needsUpdate: boolean;
  }

  export class DataTexture extends Texture {
    constructor(data: BufferSource, width: number, height: number, format?: number);
    dispose(): void;
  }

  export const RGBAFormat: number;
  export const RepeatWrapping: number;
  export const ClampToEdgeWrapping: number;
  export const SRGBColorSpace: string;
  export const FrontSide: number;

  export type Wrapping = typeof RepeatWrapping | typeof ClampToEdgeWrapping | number;

  export interface IUniform<T = unknown> {
    value: T;
  }

  export interface ShaderMaterialParameters {
    uniforms?: Record<string, IUniform>;
    vertexShader?: string;
    fragmentShader?: string;
    transparent?: boolean;
    depthTest?: boolean;
    depthWrite?: boolean;
    polygonOffset?: boolean;
    polygonOffsetFactor?: number;
    polygonOffsetUnits?: number;
    toneMapped?: boolean;
    side?: number;
  }

  export class ShaderMaterial {
    constructor(params?: ShaderMaterialParameters);
    uniforms: Record<string, IUniform | undefined>;
    userData: Record<string, unknown>;
    needsUpdate: boolean;
    premultipliedAlpha: boolean;
    dispose(): void;
  }

  export class Object3D {
    name: string;
    uuid: string;
    userData: Record<string, unknown>;
    renderOrder: number;
    matrixAutoUpdate: boolean;
    matrix: Matrix4;
    frustumCulled: boolean;
    position: Vector3;
    rotation: Euler;
    add(object: Object3D): this;
    removeFromParent(): this;
    traverse(callback: (object: Object3D) => void): void;
  }

  export class Mesh extends Object3D {
    constructor(geometry?: unknown, material?: unknown);
    geometry: unknown;
  }

  export class Scene extends Object3D {}

  export class OrthographicCamera extends Object3D {
    constructor(
      left: number,
      right: number,
      top: number,
      bottom: number,
      near?: number,
      far?: number,
    );
    position: Vector3;
    rotation: Euler;
    left: number;
    right: number;
    top: number;
    bottom: number;
    near: number;
    far: number;
    projectionMatrix: Matrix4;
    matrixWorldInverse: Matrix4;
    updateProjectionMatrix(): void;
    updateMatrixWorld(force?: boolean): void;
  }
}
