import { SparkControls } from '@sparkjsdev/spark';
import * as THREE from 'three';

/**
 * Navegação em primeira pessoa (C2 do plano do editor de splats).
 *
 * Wrapper fino sobre o `SparkControls` do Spark 2.1: WASD/setas movem a
 * câmera, Q/E sobem/descem (eixos da câmera), PageUp/PageDown idem,
 * Shift acelera (×5), Ctrl desacelera (×1/5), CapsLock acelera (×10).
 * O arraste vira "look" (gira a vista), a roda avança e o duplo-clique
 * dispara `onFocus` para quem quiser centralizar no ponto clicado.
 *
 * O OrbitControls continua dono do modo órbita: quem ativa este controle
 * deve desabilitá-lo e manter `controls.target` acompanhando a câmera
 * (`pivotAhead`) — ver ViewerController.
 */
export interface FlyFocusPoint {
  /** Posição do duplo-clique em pixels relativos ao canvas. */
  position: { x: number; y: number };
}

export class FlyControls {
  readonly camera: THREE.PerspectiveCamera;

  private readonly spark: SparkControls;
  private focusHandler: ((point: FlyFocusPoint) => void) | null = null;
  private active = false;

  constructor(options: { canvas: HTMLCanvasElement; camera: THREE.PerspectiveCamera }) {
    this.camera = options.camera;
    this.spark = new SparkControls({ canvas: options.canvas });
    this.spark.pointerControls.doublePress = ({ position }) => {
      this.focusHandler?.({ position: { x: position.x, y: position.y } });
    };
    this.applyEnabled(false);
  }

  setEnabled(enabled: boolean): void {
    if (enabled === this.active) {
      return;
    }
    this.applyEnabled(enabled);
  }

  get enabled(): boolean {
    return this.active;
  }

  /** Unidades por segundo no WASD sem modificadores (Shift/Ctrl multiplicam). */
  set moveSpeed(unitsPerSecond: number) {
    this.spark.fpsMovement.moveSpeed = unitsPerSecond;
  }

  get moveSpeed(): number {
    return this.spark.fpsMovement.moveSpeed;
  }

  /** Unidades por pixel de arraste (slide com botão do meio/direito). */
  set slideSpeed(unitsPerPixel: number) {
    this.spark.pointerControls.slideSpeed = unitsPerPixel;
  }

  /** Unidades por clique de roda (avançar/recuar na direção da vista). */
  set scrollSpeed(unitsPerTick: number) {
    this.spark.pointerControls.scrollSpeed = unitsPerTick;
  }

  onFocus(handler: (point: FlyFocusPoint) => void): void {
    this.focusHandler = handler;
  }

  /** Chame por frame com o delta em segundos; true = a câmera mudou. */
  update(deltaSeconds: number): boolean {
    if (!this.active || !(deltaSeconds > 0)) {
      return false;
    }
    return this.spark.update(this.camera, this.camera);
  }

  dispose(): void {
    this.applyEnabled(false);
    this.focusHandler = null;
  }

  /**
   * Ao ligar, zera acumulados (a roda do PointerControls continua
   * somando mesmo com `enable=false` — um acúmulo viraria um salto de
   * dolly no primeiro frame). Ao desligar, solta teclas e gestos presos.
   */
  private applyEnabled(enabled: boolean): void {
    this.active = enabled;
    this.spark.fpsMovement.enable = enabled;
    this.spark.fpsMovement.keydown = {};
    this.spark.fpsMovement.keycode = {};
    const pointer = this.spark.pointerControls;
    pointer.enable = enabled;
    pointer.scroll.set(0, 0, 0);
    pointer.rotateVelocity.set(0, 0, 0);
    pointer.moveVelocity.set(0, 0, 0);
    pointer.rotating = null;
    pointer.sliding = null;
    pointer.lastDown = null;
  }
}
