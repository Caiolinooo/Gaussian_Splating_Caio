import {
  ClampToEdgeWrapping,
  Color,
  DataTexture,
  Euler,
  FrontSide,
  Matrix4,
  Mesh,
  OrthographicCamera,
  RGBAFormat,
  RepeatWrapping,
  SRGBColorSpace,
  ShaderMaterial,
  Vector2,
  Vector3,
  type IUniform,
  type Texture,
} from 'three';

import { resolveProjectorSizeScene, resolveTiling } from '../physicalTiling';
import { overlayFragmentShader, overlayVertexShader } from '../shaders/sources';
import { blendModeToIndex, overlayKindToIndex, type Overlay } from '../types';
import type { UnitsPort } from '../units-port';

/** Ordem de render padrão: depois do splat, depth-test ligado, depthWrite off. */
export const OVERLAY_RENDER_ORDER_BASE = 2000;

export interface ProjectiveDecalOptions {
  overlay: Overlay;
  units: UnitsPort;
  targets: Mesh[];
  texture?: Texture | null;
  renderOrder?: number;
}

const LOOK_LOCAL = new Vector3(0, 0, -1);
const _euler = new Euler();
const _look = new Vector3();
const _center = new Vector3();
const _projView = new Matrix4();
const _color = new Color();

function requireUniform<T>(material: ShaderMaterial, name: string): IUniform<T> {
  const uniform = material.uniforms[name];
  if (!uniform) {
    throw new Error(`Missing overlay uniform: ${name}`);
  }
  return uniform as IUniform<T>;
}

function createWhiteTexture(): DataTexture {
  const data = new Uint8Array([255, 255, 255, 255]);
  const texture = new DataTexture(data, 1, 1, RGBAFormat);
  texture.needsUpdate = true;
  texture.colorSpace = SRGBColorSpace;
  return texture;
}

/**
 * Atualiza a câmera ortográfica para uma caixa centrada em `position`
 * (convenção DecalGeometry: o hit fica no centro; −Z local é o eixo de projeção).
 */
export function syncProjectorCamera(
  camera: OrthographicCamera,
  overlay: Overlay,
  units: UnitsPort,
): void {
  const { width, height, depth } = resolveProjectorSizeScene(overlay, units);
  const hw = width / 2;
  const hh = height / 2;
  const near = Math.max(depth * 0.001, 1e-4);
  camera.left = -hw;
  camera.right = hw;
  camera.top = hh;
  camera.bottom = -hh;
  camera.near = near;
  camera.far = Math.max(depth, near + 1e-3);

  _euler.set(
    overlay.transform.rotation.x,
    overlay.transform.rotation.y,
    overlay.transform.rotation.z,
    'XYZ',
  );
  _look.copy(LOOK_LOCAL).applyEuler(_euler);
  _center.set(
    overlay.transform.position.x,
    overlay.transform.position.y,
    overlay.transform.position.z,
  );
  camera.position.copy(_center).addScaledVector(_look, -depth / 2);
  camera.rotation.copy(_euler);
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);
}

/**
 * Decal projetivo sobre a malha proxy via shader (não usa DecalGeometry).
 *
 * A geometria da proxy é reutilizada; UVs vêm da câmera virtual. Preview
 * atualiza só uniforms (tiling, cor, pose, máscara) — sem rebuild.
 */
export class ProjectiveDecal {
  readonly material: ShaderMaterial;
  readonly projector: OrthographicCamera;
  readonly meshes: Mesh[] = [];

  private readonly fallbackTexture: DataTexture;
  private ownsFallback = true;
  private userTexture: Texture | null = null;

  constructor(options: ProjectiveDecalOptions) {
    this.fallbackTexture = createWhiteTexture();
    this.projector = new OrthographicCamera(-0.5, 0.5, 0.5, -0.5, 0.001, 1);
    this.material = new ShaderMaterial({
      uniforms: {
        uMap: { value: this.fallbackTexture },
        uColor: { value: new Color(1, 1, 1) },
        uOpacity: { value: 1 },
        uRepeat: { value: new Vector2(1, 1) },
        uOffset: { value: new Vector2(0, 0) },
        uBlendMode: { value: 0 },
        uKind: { value: 0 },
        uHasTexture: { value: false },
        uMaskByNormal: { value: true },
        uNormalThreshold: { value: 0.5 },
        uProjectorDirection: { value: new Vector3(0, 0, -1) },
        uPremultiply: { value: false },
        uProjectorMatrix: { value: new Matrix4() },
      },
      vertexShader: overlayVertexShader,
      fragmentShader: overlayFragmentShader,
      transparent: true,
      depthTest: true,
      depthWrite: false,
      polygonOffset: true,
      polygonOffsetFactor: -1,
      polygonOffsetUnits: -1,
      toneMapped: false,
      side: FrontSide,
    });

    this.setTargets(options.targets);
    this.setRenderOrder(options.renderOrder ?? OVERLAY_RENDER_ORDER_BASE);
    if (options.texture) {
      this.setTexture(options.texture);
    }
    this.applyOverlay(options.overlay, options.units);
  }

  /**
   * Recria os wrappers sobre as malhas-alvo (mesmo BufferGeometry, material compartilhado).
   * Chamado só quando `targetSurface` muda — não no preview.
   */
  setTargets(targets: Mesh[]): void {
    this.detachMeshes();
    for (const target of targets) {
      const wrapper = new Mesh(target.geometry, this.material);
      wrapper.name = `overlay:${target.name || target.uuid}`;
      wrapper.matrixAutoUpdate = false;
      wrapper.matrix.identity();
      wrapper.frustumCulled = true;
      wrapper.renderOrder =
        (this.material.userData['renderOrder'] as number | undefined) ?? OVERLAY_RENDER_ORDER_BASE;
      wrapper.userData['gsOverlayWrapper'] = true;
      target.add(wrapper);
      this.meshes.push(wrapper);
    }
  }

  /** Ordem de composição (maior = na frente). Depth-test contra o splat permanece. */
  setRenderOrder(order: number): void {
    this.material.userData['renderOrder'] = order;
    for (const mesh of this.meshes) {
      mesh.renderOrder = order;
    }
  }

  /**
   * Troca o mapa. Texturas do loader não são disposed aqui (o app é dono).
   */
  setTexture(texture: Texture | null): void {
    this.userTexture = texture;
    const map = texture ?? this.fallbackTexture;
    requireUniform<Texture>(this.material, 'uMap').value = map;
    requireUniform<boolean>(this.material, 'uHasTexture').value = texture !== null;
    this.material.needsUpdate = true;
  }

  /**
   * Aplica o modelo aos uniforms (preview em tempo real — sem rebuild de geometria).
   */
  applyOverlay(overlay: Overlay, units: UnitsPort): void {
    syncProjectorCamera(this.projector, overlay, units);
    _projView.multiplyMatrices(this.projector.projectionMatrix, this.projector.matrixWorldInverse);
    requireUniform<Matrix4>(this.material, 'uProjectorMatrix').value.copy(_projView);

    _look.copy(LOOK_LOCAL).applyEuler(this.projector.rotation);
    requireUniform<Vector3>(this.material, 'uProjectorDirection').value.copy(_look);

    const tint = overlay.kind === 'paint' ? overlay.color : (overlay.color ?? '#ffffff');
    _color.set(tint);
    requireUniform<Color>(this.material, 'uColor').value.copy(_color);
    requireUniform<number>(this.material, 'uOpacity').value = overlay.opacity;
    requireUniform<number>(this.material, 'uBlendMode').value = blendModeToIndex(overlay.blendMode);
    requireUniform<number>(this.material, 'uKind').value = overlayKindToIndex(overlay.kind);

    const tiling = resolveTiling(overlay, units);
    requireUniform<Vector2>(this.material, 'uRepeat').value.set(tiling.repeatU, tiling.repeatV);
    requireUniform<Vector2>(this.material, 'uOffset').value.set(tiling.offsetU, tiling.offsetV);

    requireUniform<boolean>(this.material, 'uMaskByNormal').value = overlay.maskByNormal.enabled;
    requireUniform<number>(this.material, 'uNormalThreshold').value =
      overlay.maskByNormal.threshold;

    const isSticker = overlay.kind === 'sticker';
    requireUniform<boolean>(this.material, 'uPremultiply').value = isSticker;
    this.material.premultipliedAlpha = isSticker;

    const map = this.userTexture;
    if (map) {
      map.wrapS = map.wrapT = overlay.kind === 'wallpaper' ? RepeatWrapping : ClampToEdgeWrapping;
      map.colorSpace = SRGBColorSpace;
      map.needsUpdate = true;
    }

    const hasTexture =
      this.userTexture !== null && (overlay.kind !== 'paint' || overlay.textureRef !== undefined);
    requireUniform<boolean>(this.material, 'uHasTexture').value = hasTexture;
  }

  dispose(): void {
    this.detachMeshes();
    this.material.dispose();
    if (this.ownsFallback) {
      this.fallbackTexture.dispose();
      this.ownsFallback = false;
    }
  }

  private detachMeshes(): void {
    for (const mesh of this.meshes) {
      mesh.removeFromParent();
    }
    this.meshes.length = 0;
  }
}
