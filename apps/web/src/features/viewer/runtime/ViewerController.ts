import { OverlayManager, OverlayValidationError, type OverlayDraft } from '@gs/overlays';
import {
  createSplatRenderer,
  createTRS,
  pickClosest,
  pickMeshes,
  SceneManager,
  toShDegree,
  TransformGizmo,
  type CalibrationJson,
  type LengthUnit,
  type RendererBackendKind,
  type SplatFormat,
  type SplatHandle,
  type SplatQuality,
  type SplatRenderer,
  type TRS,
} from '@gs/viewer';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

import { createOverlayUnitsPort, createViewerUnitsPort, toMeters } from '../../../lib/unitsBinding';
import {
  downloadJobPackage as fetchJobPackageDownload,
  extractCalibrationExtras,
  fetchJobArtifact,
  fetchJobSceneDocument,
  fetchScene,
  isMissingSplatArtifact,
  mergeCalibrationForApi,
  MISSING_SPLAT_USER_MESSAGE,
  putScene,
  type CalibrationExtras,
  type SceneApiDocument,
} from '../../../lib/viewerApi';
import { worldBoundingSize, eulerDegreesFromQuaternion } from '../../editing/bbox/liveBounds';
import { loadGlbIntoHost, nodeNameFromFile } from '../../editing/glb/importGlb';
import { useEditingStore } from '../../editing/store/editingStore';
import {
  isCalibrated,
  metersFromScene,
  rootScaleFromCalibration,
  scaleFactorFromSceneAndMeters,
  shouldCompensateObjects,
  suggestedReferencePoints,
} from '../../calibration/math/scaleFactor';
import { distance3, type ScenePoint } from '../../calibration/math/tapeMath';
import { useCalibrationStore, wasGateConfirmed } from '../../calibration/store/calibrationStore';
import { useTapeStore } from '../../calibration/store/tapeStore';
import { snapTranslateMeters } from '../../calibration/store/unitsPreference';
import { extractOverlayDocument, toSceneOverlaySummaries } from '../../overlays/overlayPersist';
import { useOverlayStore } from '../../overlays/store/overlayStore';
import { useViewerStore } from '../store/viewerStore';
import type { CameraPreset, WorkspaceTool } from '../types';
import { applyCameraPreset } from './cameraPresets';
import { asObject3D, createThreeHost, resolveNodeId, setNodeId } from './createThreeHost';
import { pointerToNdc, rayFromPointer } from './ndc';
import { TapeVisuals } from './tapeVisuals';

export interface BootOptions {
  jobId?: string;
  sceneId?: string;
  forceBackend?: RendererBackendKind;
  initialTool?: WorkspaceTool;
}

const CLICK_SLOP_PX = 4;

export class ViewerController {
  readonly scene = new THREE.Scene();
  readonly camera: THREE.PerspectiveCamera;
  readonly webgl: THREE.WebGLRenderer;
  readonly controls: OrbitControls;
  readonly sceneManager: SceneManager;
  readonly overlayManager: OverlayManager;
  readonly proxyRoot = new THREE.Group();
  readonly canvas: HTMLCanvasElement;

  splatRenderer: SplatRenderer | null = null;
  splatHandle: SplatHandle | null = null;
  gizmo: TransformGizmo | null = null;

  private readonly tapeVisuals: TapeVisuals;
  private readonly selectionHelper: THREE.BoxHelper;
  private readonly viewerUnits = createViewerUnitsPort();
  private readonly objectUrls = new Set<string>();
  private resizeObserver: ResizeObserver | null = null;
  private raf = 0;
  private disposed = false;
  private pointerDown: { x: number; y: number } | null = null;
  private lastFrame = performance.now();
  private fpsFrames = 0;
  private fpsElapsed = 0;
  private hoverPoint: ScenePoint | null = null;
  private unsubScene: (() => void) | null = null;
  private unsubOverlays: (() => void) | null = null;
  private unsubTape: (() => void) | null = null;
  private unsubEditing: (() => void) | null = null;
  private unsubUnits: (() => void) | null = null;
  private extras: CalibrationExtras = {};

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    this.scene.background = new THREE.Color(0x070b16);
    this.camera = new THREE.PerspectiveCamera(50, 1, 0.05, 400);
    this.camera.position.set(4.2, 3.3, 4.2);

    this.webgl = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    this.webgl.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.webgl.outputColorSpace = THREE.SRGBColorSpace;

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.target.set(0, 1, 0);

    this.scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const key = new THREE.DirectionalLight(0xffffff, 1.1);
    key.position.set(4, 8, 3);
    this.scene.add(key);

    const grid = new THREE.GridHelper(10, 10, 0x334155, 0x1e293b);
    grid.name = 'meter-grid';
    this.scene.add(grid);

    this.sceneManager = new SceneManager({
      units: this.viewerUnits,
      createHost: createThreeHost,
    });
    const root = asObject3D(this.sceneManager.root);
    if (!root) {
      throw new Error('Falha ao criar o nó-raiz da cena.');
    }
    this.scene.add(root);

    this.proxyRoot.name = 'proxy-root';
    root.add(this.proxyRoot);
    mountDefaultProxy(this.proxyRoot);

    const overlayUnits = createOverlayUnitsPort(() => {
      const factor = useCalibrationStore.getState().calibration.scaleFactor;
      return factor && factor > 0 ? factor : 1;
    });
    const textureLoader = new THREE.TextureLoader();
    this.overlayManager = new OverlayManager({
      units: overlayUnits,
      scene: this.scene,
      proxyRoot: this.proxyRoot,
      textureLoader: (ref) => textureLoader.loadAsync(ref),
    });

    this.tapeVisuals = new TapeVisuals(root);
    this.selectionHelper = new THREE.BoxHelper(root, 0x22c55e);
    this.selectionHelper.visible = false;
    this.scene.add(this.selectionHelper);

    this.gizmo = new TransformGizmo(this.camera, canvas, this.scene, {
      onChange: (trs) => this.onGizmoChange(trs),
      onDragEnd: (trs) => this.onGizmoEnd(trs),
      onDraggingChanged: (dragging) => {
        this.controls.enabled = !dragging;
        useEditingStore.getState().setDragging(dragging);
      },
    });

    this.bindDom();
    this.bindStores();
    this.fitRenderer();
    applyCameraPreset(this.camera, this.controls, 'iso');
  }

  async boot(options: BootOptions): Promise<void> {
    const store = useViewerStore.getState();
    store.setIds({ jobId: options.jobId ?? null, sceneId: options.sceneId ?? null });
    store.setLoad('scene', 0, 'Abrindo a cena…');
    useCalibrationStore.getState().setGatePhase('hidden');

    if (options.initialTool === 'tape') {
      useTapeStore.getState().toggleActive(true);
    }
    if (options.initialTool === 'overlay') {
      useOverlayStore.getState().patchDraft({ placementMode: true });
    }

    try {
      const created = await createSplatRenderer(
        { scene: this.scene, renderer: this.webgl, camera: this.camera },
        { force: options.forceBackend },
      );
      this.splatRenderer = created.renderer;
      store.setBackend(created.detection);
      store.setQuality(this.splatRenderer.getQuality());
    } catch (error) {
      store.setError(
        error instanceof Error ? error.message : 'Renderer 3D indisponível neste navegador.',
      );
      this.startLoop();
      return;
    }

    try {
      if (options.sceneId) {
        await this.openScene(options.sceneId, options.jobId);
      } else if (options.jobId) {
        await this.loadSplatFromJob(options.jobId);
        this.installEmptyBackground(options.jobId);
        await this.applyExportedScene(options.jobId);
        this.syncCalibrationFromManager();
        this.decideGate(options.sceneId);
      } else {
        store.setLoad('ready', 1, '');
        this.syncCalibrationFromManager();
        useCalibrationStore.getState().setGatePhase('blocked');
      }
    } catch (error) {
      useCalibrationStore.getState().setGatePhase('hidden');
      if (isMissingSplatArtifact(error)) {
        store.setError(MISSING_SPLAT_USER_MESSAGE);
      } else {
        store.setError(error instanceof Error ? error.message : 'Falha ao carregar a cena.');
      }
    }

    this.startLoop();
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    this.resizeObserver?.disconnect();
    this.canvas.removeEventListener('pointerdown', this.onPointerDown);
    this.canvas.removeEventListener('pointermove', this.onPointerMove);
    this.canvas.removeEventListener('pointerup', this.onPointerUp);
    window.removeEventListener('keydown', this.onKeyDown);
    this.unsubScene?.();
    this.unsubOverlays?.();
    this.unsubTape?.();
    this.unsubEditing?.();
    this.unsubUnits?.();
    this.gizmo?.dispose();
    this.tapeVisuals.dispose();
    this.overlayManager.dispose();
    this.splatRenderer?.dispose();
    this.controls.dispose();
    this.webgl.dispose();
    for (const url of this.objectUrls) {
      URL.revokeObjectURL(url);
    }
    this.objectUrls.clear();
  }

  setCameraPreset(preset: CameraPreset): void {
    applyCameraPreset(this.camera, this.controls, preset);
    useViewerStore.getState().setCameraPreset(preset);
  }

  setQuality(patch: Partial<SplatQuality>): void {
    if (!this.splatRenderer) {
      return;
    }
    this.splatRenderer.setQuality(patch);
    useViewerStore.getState().setQuality(this.splatRenderer.getQuality());
  }

  setPlaybackTime(normalized: number): void {
    const clamped = Math.max(0, Math.min(1, normalized));
    this.splatRenderer?.setTime(clamped);
    const current = this.sceneManager.getState().temporal;
    const next = { ...current, currentTime: clamped };
    this.sceneManager.setTemporal(next);
    useViewerStore.getState().setTemporal(next);
  }

  setRelightPreview(enabled: boolean): void {
    this.splatRenderer?.setRelightEnabled(enabled);
    const current = this.sceneManager.getState().relight;
    const next = { ...current, enabled };
    this.sceneManager.setRelight(next);
    useViewerStore.getState().setRelight(next);
  }

  downloadSceneJson(): void {
    const json = this.sceneManager.toJSON();
    const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    const id = this.sceneManager.getState().id || 'cena';
    anchor.href = url;
    anchor.download = `${id}.scene.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async downloadJobPackage(): Promise<void> {
    const jobId = useViewerStore.getState().jobId;
    if (!jobId) {
      return;
    }
    try {
      await fetchJobPackageDownload(jobId);
    } catch (error) {
      useViewerStore
        .getState()
        .setError(error instanceof Error ? error.message : 'Falha ao baixar o pacote da cena.');
    }
  }

  cycleShDegree(): void {
    if (!this.splatRenderer) {
      return;
    }
    const max = this.splatRenderer.capabilities.maxShDegree;
    const current = this.splatRenderer.getQuality().shDegree;
    const next = toShDegree((current + 1) % (max + 1));
    this.setQuality({ shDegree: next });
  }

  selectNode(id: string | null): void {
    useEditingStore.getState().select(id);
    this.syncSelection();
  }

  undo(): void {
    if (this.sceneManager.canUndo()) {
      this.sceneManager.undo();
      useViewerStore.getState().markDirty();
    }
  }

  redo(): void {
    if (this.sceneManager.canRedo()) {
      this.sceneManager.redo();
      useViewerStore.getState().markDirty();
    }
  }

  async importGlb(file: File): Promise<void> {
    if (!isCalibrated(useCalibrationStore.getState().calibration)) {
      useViewerStore.getState().setError('Calibre a cena com a trena antes de inserir objetos.');
      return;
    }
    const node = this.sceneManager.addNode({
      name: nodeNameFromFile(file),
      kind: 'glb',
      uri: 'pending',
      format: 'glb',
    });
    const host = asObject3D(this.sceneManager.getHost(node.id));
    if (!host) {
      return;
    }
    setNodeId(host, node.id);
    const url = await loadGlbIntoHost(file, host);
    this.objectUrls.add(url);
    this.sceneManager.rename(node.id, nodeNameFromFile(file));
    useViewerStore.getState().markDirty();
    this.selectNode(node.id);
  }

  applyManualReference(measureId: string, realValue: number, unit: LengthUnit): void {
    const measure = useTapeStore.getState().measures.find((item) => item.id === measureId);
    if (!measure) {
      return;
    }
    const sceneDistance = distance3(measure.a, measure.b);
    const meters = toMeters(realValue, unit);
    const scaleFactor = scaleFactorFromSceneAndMeters(sceneDistance, meters);
    this.commitCalibration(
      {
        scaleFactor,
        source: 'manual',
        confidence: 1,
        reference: {
          sceneDistance,
          realLengthMm: String(meters * 1000),
        },
      },
      {},
    );
    useTapeStore.getState().setReferenceOpen(false);
  }

  confirmAutoCalibration(): void {
    const { calibration } = useCalibrationStore.getState();
    this.commitCalibration({ ...calibration, source: 'auto-height' }, this.extras);
    const sceneId = useViewerStore.getState().sceneId;
    if (sceneId) {
      useCalibrationStore.getState().markConfirmed(sceneId);
    } else {
      useCalibrationStore.getState().setGatePhase('hidden');
    }
  }

  adjustAutoCalibration(realMeters: number): void {
    const { a, b } = suggestedReferencePoints();
    const sceneDistance = distance3(a, b);
    const scaleFactor = scaleFactorFromSceneAndMeters(sceneDistance, realMeters);
    this.commitCalibration(
      {
        scaleFactor,
        source: 'manual',
        confidence: 1,
        reference: { sceneDistance, realLengthMm: String(realMeters * 1000) },
      },
      this.extras,
    );
    const sceneId = useViewerStore.getState().sceneId;
    if (sceneId) {
      useCalibrationStore.getState().markConfirmed(sceneId);
    } else {
      useCalibrationStore.getState().setGatePhase('hidden');
    }
  }

  startManualCalibration(): void {
    useCalibrationStore.getState().setGatePhase('hidden');
    useTapeStore.getState().toggleActive(true);
  }

  commitCalibration(next: CalibrationJson, extras: CalibrationExtras): void {
    const previous = this.sceneManager.getState().calibration;
    if (shouldCompensateObjects(previous, next) && previous.scaleFactor && next.scaleFactor) {
      const oldF = previous.scaleFactor;
      const newF = next.scaleFactor;
      for (const node of this.sceneManager.getState().nodes) {
        if (node.locked) {
          continue;
        }
        this.sceneManager.setTRS(node.id, {
          position: {
            x: node.trs.position.x * (oldF / newF),
            y: node.trs.position.y * (oldF / newF),
            z: node.trs.position.z * (oldF / newF),
          },
          rotation: node.trs.rotation,
          scale: {
            x: node.trs.scale.x * (oldF / newF),
            y: node.trs.scale.y * (oldF / newF),
            z: node.trs.scale.z * (oldF / newF),
          },
        });
      }
    }
    this.sceneManager.setCalibration(next);
    this.extras = extras;
    useCalibrationStore.getState().setCalibration(next, extras);
    this.syncRootScale();
    this.refreshOverlayUniforms();
    this.syncGizmoSnap();
    useViewerStore.getState().markDirty();
  }

  applyNodeTrs(nodeId: string, trs: TRS): void {
    this.sceneManager.setTRS(nodeId, trs);
    useViewerStore.getState().markDirty();
  }

  renameNode(id: string, name: string): void {
    this.sceneManager.rename(id, name);
    useViewerStore.getState().markDirty();
  }

  duplicateNode(id: string): void {
    if (!isCalibrated(useCalibrationStore.getState().calibration)) {
      useViewerStore.getState().setError('Calibre a cena antes de duplicar objetos.');
      return;
    }
    const copy = this.sceneManager.duplicate(id);
    useViewerStore.getState().markDirty();
    this.selectNode(copy.id);
  }

  deleteNode(id: string): void {
    this.sceneManager.delete(id);
    if (useEditingStore.getState().selectedNodeId === id) {
      this.selectNode(null);
    }
    useViewerStore.getState().markDirty();
  }

  setNodeVisible(id: string, visible: boolean): void {
    this.sceneManager.setVisible(id, visible);
    useViewerStore.getState().markDirty();
  }

  async saveScene(): Promise<void> {
    const viewer = useViewerStore.getState();
    const sceneId = viewer.sceneId ?? this.sceneManager.getState().id;
    viewer.setIds({ sceneId });
    viewer.setSaving(true);
    const overlayDocument = this.overlayManager.serialize();
    this.sceneManager.setOverlays(toSceneOverlaySummaries(overlayDocument.overlays));
    const base = this.sceneManager.toDocument();
    const payload: SceneApiDocument = {
      ...base,
      calibration: mergeCalibrationForApi(base.calibration, this.extras),
      overlayDocument,
    };
    try {
      await putScene(sceneId, payload);
      viewer.markSaved();
    } catch (error) {
      viewer.setSaving(false);
      viewer.setError(error instanceof Error ? error.message : 'Falha ao salvar a cena.');
    }
  }

  async openSceneById(sceneId: string): Promise<void> {
    useViewerStore.getState().setIds({ sceneId });
    await this.openScene(sceneId, useViewerStore.getState().jobId ?? undefined);
  }

  placeOverlayFromDraft(point: ScenePoint, rotation: ScenePoint): void {
    if (!isCalibrated(useCalibrationStore.getState().calibration)) {
      useViewerStore.getState().setError('Calibre a cena antes de aplicar overlays.');
      return;
    }
    const draft = useOverlayStore.getState().draft;
    try {
      const created = this.overlayManager.add(buildOverlayDraft(draft, point, rotation));
      useOverlayStore.getState().setOverlays(this.overlayManager.list());
      useOverlayStore.getState().select(created.id);
      useOverlayStore.getState().patchDraft({ placementMode: false });
      useOverlayStore.getState().setError(null);
      this.syncOverlaySummaries();
      useViewerStore.getState().markDirty();
    } catch (error) {
      const message =
        error instanceof OverlayValidationError
          ? error.issues.join(' ')
          : error instanceof Error
            ? error.message
            : 'Não foi possível criar o overlay.';
      useOverlayStore.getState().setError(message);
    }
  }

  previewSelectedOverlay(): void {
    const { selectedId, draft } = useOverlayStore.getState();
    if (!selectedId) {
      return;
    }
    try {
      this.overlayManager.preview(selectedId, {
        opacity: draft.opacity,
        blendMode: draft.blendMode,
        color: draft.color,
        physicalSize: {
          width: { value: draft.width, unit: draft.sizeUnit },
          height: { value: draft.height, unit: draft.sizeUnit },
        },
        maskByNormal: { enabled: draft.maskEnabled },
      });
      useOverlayStore.getState().setOverlays(this.overlayManager.list());
    } catch {
      // preview inválido — o editor mostra o erro ao aplicar
    }
  }

  removeOverlay(id: string): void {
    this.overlayManager.remove(id);
    useOverlayStore.getState().setOverlays(this.overlayManager.list());
    if (useOverlayStore.getState().selectedId === id) {
      useOverlayStore.getState().select(null);
    }
    this.syncOverlaySummaries();
    useViewerStore.getState().markDirty();
  }

  suggestedMeters(): number {
    const factor = useCalibrationStore.getState().calibration.scaleFactor;
    if (!factor) {
      return 1;
    }
    return metersFromScene(
      distance3(suggestedReferencePoints().a, suggestedReferencePoints().b),
      factor,
    );
  }

  private async openScene(sceneId: string, jobId?: string): Promise<void> {
    const store = useViewerStore.getState();
    store.setLoad('scene', 0.1, 'Baixando o JSON da cena…');
    const payload = await fetchScene(sceneId);
    if (payload) {
      this.extras = extractCalibrationExtras(payload.calibration);
      this.sceneManager.fromDocument(payload);
      store.setSceneName(this.sceneManager.getState().name);
      const overlayDoc = extractOverlayDocument(payload);
      if (overlayDoc) {
        this.overlayManager.loadDocument(overlayDoc);
        useOverlayStore.getState().setOverlays(this.overlayManager.list());
      }
    }
    const background = this.sceneManager.getState().backgroundSplat;
    if (background?.uri.startsWith('http') || background?.uri.startsWith('/')) {
      await this.loadSplatFromUrl(background.uri, background.format);
    } else if (jobId) {
      await this.loadSplatFromJob(jobId);
      if (!background) {
        this.installEmptyBackground(jobId);
      }
    } else {
      store.setLoad('ready', 1, '');
    }
    this.syncCalibrationFromManager();
    this.syncTemporalFromManager();
    this.decideGate(sceneId);
    this.tagHosts();
  }

  private async applyExportedScene(jobId: string): Promise<void> {
    try {
      const document = await fetchJobSceneDocument(jobId);
      if (!document) {
        return;
      }
      this.sceneManager.setTemporal(document.temporal);
      this.sceneManager.setRelight(document.relight);
      if (document.calibration.source !== 'none') {
        this.sceneManager.setCalibration(document.calibration);
      }
      this.syncTemporalFromManager();
    } catch {
      // JSON de cena ainda não existe — o splat sozinho basta.
    }
  }

  private syncTemporalFromManager(): void {
    const state = this.sceneManager.getState();
    useViewerStore.getState().setTemporal(state.temporal);
    useViewerStore.getState().setRelight(state.relight);
    this.splatRenderer?.setTime(state.temporal.currentTime);
    this.splatRenderer?.setRelightEnabled(state.relight.enabled);
  }

  private async loadSplatFromJob(jobId: string): Promise<void> {
    const store = useViewerStore.getState();
    store.setLoad('artifact', 0, 'Baixando o splat…');
    try {
      const artifact = await fetchJobArtifact(jobId, 'ksplat', {
        onProgress: (ratio) => store.setLoad('artifact', ratio, 'Baixando o .ksplat…'),
      });
      await this.ingestSplatBuffer(artifact.buffer, artifact.kind);
    } catch (ksplatError) {
      try {
        const artifact = await fetchJobArtifact(jobId, 'ply', {
          onProgress: (ratio) => store.setLoad('artifact', ratio, 'Baixando o .ply…'),
        });
        await this.ingestSplatBuffer(artifact.buffer, artifact.kind);
      } catch {
        throw ksplatError;
      }
    }
  }

  private async loadSplatFromUrl(url: string, format: SplatFormat): Promise<void> {
    const store = useViewerStore.getState();
    store.setLoad('splat', 0, 'Carregando o splat…');
    if (!this.splatRenderer) {
      return;
    }
    const handle = await this.splatRenderer.load(
      { url, format },
      {
        onProgress: (progress) => store.setLoad('splat', progress.ratio, 'Carregando o splat…'),
      },
    );
    this.attachSplat(handle);
  }

  private async ingestSplatBuffer(buffer: ArrayBuffer, format: SplatFormat): Promise<void> {
    const store = useViewerStore.getState();
    if (!this.splatRenderer) {
      return;
    }
    store.setLoad('splat', 0, 'Preparando o renderer…');
    const handle = await this.splatRenderer.load(
      { buffer, format },
      {
        onProgress: (progress) => store.setLoad('splat', progress.ratio, 'Carregando gaussianas…'),
      },
    );
    this.attachSplat(handle);
  }

  private attachSplat(handle: SplatHandle): void {
    if (!this.splatRenderer) {
      return;
    }
    const root = asObject3D(this.sceneManager.root);
    if (root) {
      this.splatRenderer.addToScene(handle, root);
    }
    this.splatHandle = handle;
    useViewerStore
      .getState()
      .setHud({ gaussianCount: this.splatRenderer.getGaussianCount(handle) });
    useViewerStore.getState().setLoad('ready', 1, '');
  }

  private installEmptyBackground(jobId: string): void {
    this.sceneManager.setBackground({
      id: `bg-${jobId}`,
      name: 'Splat de fundo',
      uri: `job:${jobId}`,
      format: 'ksplat',
      visible: true,
    });
  }

  private syncCalibrationFromManager(): void {
    const calibration = this.sceneManager.getState().calibration;
    useCalibrationStore.getState().setCalibration(calibration, this.extras);
    this.syncRootScale();
    this.syncGizmoSnap();
  }

  private decideGate(sceneId?: string): void {
    const calibration = this.sceneManager.getState().calibration;
    const store = useCalibrationStore.getState();
    if (!isCalibrated(calibration)) {
      store.setGatePhase('blocked');
      return;
    }
    if (calibration.source === 'auto-height' && sceneId && !wasGateConfirmed(sceneId)) {
      store.setGatePhase('auto-confirm');
      return;
    }
    store.setGatePhase('hidden');
  }

  private syncRootScale(): void {
    const root = asObject3D(this.sceneManager.root);
    if (!root) {
      return;
    }
    const scale = rootScaleFromCalibration(this.sceneManager.getState().calibration);
    root.scale.setScalar(scale);
  }

  private syncGizmoSnap(): void {
    const { unitPref } = useCalibrationStore.getState();
    const { snapEnabled, transformMode, transformSpace } = useEditingStore.getState();
    const calibrated = isCalibrated(useCalibrationStore.getState().calibration);
    const translate =
      snapEnabled && calibrated ? snapTranslateMeters(unitPref.unit) : snapEnabled ? 0.01 : null;
    this.gizmo?.setSnap({
      translate,
      rotate: snapEnabled ? Math.PI / 36 : null,
      scale: snapEnabled ? 0.05 : null,
    });
    this.gizmo?.setMode(transformMode);
    this.gizmo?.setSpace(transformSpace);
    useEditingStore.getState().setSnap({ translate });
  }

  private syncOverlaySummaries(): void {
    this.sceneManager.setOverlays(toSceneOverlaySummaries(this.overlayManager.list()));
  }

  private refreshOverlayUniforms(): void {
    for (const overlay of this.overlayManager.list()) {
      this.overlayManager.preview(overlay.id, {});
    }
  }

  private tagHosts(): void {
    const state = this.sceneManager.getState();
    if (state.backgroundSplat) {
      const host = asObject3D(this.sceneManager.getHost(state.backgroundSplat.id));
      if (host) {
        setNodeId(host, state.backgroundSplat.id);
      }
    }
    for (const node of state.nodes) {
      const host = asObject3D(this.sceneManager.getHost(node.id));
      if (host) {
        setNodeId(host, node.id);
      }
    }
  }

  private syncSelection(): void {
    const id = useEditingStore.getState().selectedNodeId;
    const host = id ? asObject3D(this.sceneManager.getHost(id)) : null;
    const locked = this.sceneManager.getOutliner().find((item) => item.id === id)?.locked === true;
    if (host && !locked) {
      this.gizmo?.attach(host);
      this.selectionHelper.setFromObject(host);
      this.selectionHelper.visible = true;
      this.pushLiveMetrics(host);
    } else {
      this.gizmo?.detach();
      this.selectionHelper.visible = false;
      useEditingStore.getState().setLiveBbox(null);
      useEditingStore.getState().setLiveTrs(null);
    }
  }

  private pushLiveMetrics(host: THREE.Object3D): void {
    const id = useEditingStore.getState().selectedNodeId;
    const node = this.sceneManager.getState().nodes.find((item) => item.id === id);
    const trs =
      node?.trs ??
      createTRS({
        position: { x: host.position.x, y: host.position.y, z: host.position.z },
        rotation: {
          x: host.quaternion.x,
          y: host.quaternion.y,
          z: host.quaternion.z,
          w: host.quaternion.w,
        },
        scale: { x: host.scale.x, y: host.scale.y, z: host.scale.z },
      });
    const euler = eulerDegreesFromQuaternion(trs.rotation);
    useEditingStore.getState().setLiveBbox(worldBoundingSize(host));
    useEditingStore.getState().setLiveTrs({
      px: trs.position.x,
      py: trs.position.y,
      pz: trs.position.z,
      rx: euler.x,
      ry: euler.y,
      rz: euler.z,
      sx: trs.scale.x,
      sy: trs.scale.y,
      sz: trs.scale.z,
    });
  }

  private onGizmoChange(trs: TRS): void {
    const host = this.gizmo?.getObject();
    if (host) {
      this.selectionHelper.setFromObject(host);
      this.pushLiveMetrics(host);
    }
    void trs;
  }

  private onGizmoEnd(trs: TRS): void {
    const id = useEditingStore.getState().selectedNodeId;
    if (!id) {
      return;
    }
    const node = this.sceneManager.getState().nodes.find((item) => item.id === id);
    if (!node || node.locked) {
      return;
    }
    this.sceneManager.setTRS(id, trs);
    useViewerStore.getState().markDirty();
  }

  private worldToLocal(point: THREE.Vector3): ScenePoint {
    const root = asObject3D(this.sceneManager.root);
    const local = point.clone();
    root?.worldToLocal(local);
    return { x: local.x, y: local.y, z: local.z };
  }

  private pickScenePoint(
    event: PointerEvent,
  ): { point: ScenePoint; normal?: ScenePoint; nodeId: string | null } | null {
    const ray = rayFromPointer(event, this.canvas, this.camera);
    const ndc = pointerToNdc(event, this.canvas);
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(new THREE.Vector2(ndc.x, ndc.y), this.camera);

    const tapeHits = raycaster.intersectObject(this.tapeVisuals.group, true);
    const proxyHits = raycaster.intersectObject(this.proxyRoot, true);
    const meshHits = pickMeshes(
      ray,
      [asObject3D(this.sceneManager.root) ?? this.scene],
      true,
    ).filter((hit) => !isHelper(hit.object) && !isProxyMesh(hit.object));
    const splatHit = this.splatRenderer?.pick(ray) ?? null;
    const unified = pickClosest(meshHits, splatHit);

    if (tapeHits[0] && useTapeStore.getState().active) {
      const obj = tapeHits[0].object;
      return {
        point: this.worldToLocal(tapeHits[0].point),
        nodeId: typeof obj.userData['gsTapeId'] === 'string' ? obj.userData['gsTapeId'] : null,
      };
    }

    if (proxyHits[0] && !unified) {
      const hit = proxyHits[0];
      const normal = hit.face
        ? hit.face.normal.clone().transformDirection(hit.object.matrixWorld)
        : new THREE.Vector3(0, 1, 0);
      return {
        point: this.worldToLocal(hit.point),
        normal: { x: normal.x, y: normal.y, z: normal.z },
        nodeId: null,
      };
    }

    if (!unified) {
      if (proxyHits[0]) {
        const hit = proxyHits[0];
        const normal = hit.face
          ? hit.face.normal.clone().transformDirection(hit.object.matrixWorld)
          : new THREE.Vector3(0, 1, 0);
        return {
          point: this.worldToLocal(hit.point),
          normal: { x: normal.x, y: normal.y, z: normal.z },
          nodeId: null,
        };
      }
      return null;
    }

    if (unified.kind === 'mesh') {
      return {
        point: this.worldToLocal(
          new THREE.Vector3(unified.mesh.point.x, unified.mesh.point.y, unified.mesh.point.z),
        ),
        nodeId: resolveNodeId(unified.mesh.object),
      };
    }
    const bg = this.sceneManager.getState().backgroundSplat;
    return {
      point: this.worldToLocal(
        new THREE.Vector3(unified.splat.point.x, unified.splat.point.y, unified.splat.point.z),
      ),
      nodeId: bg?.id ?? null,
    };
  }

  private onPointerDown = (event: PointerEvent): void => {
    if (event.button !== 0) {
      return;
    }
    this.pointerDown = { x: event.clientX, y: event.clientY };
    const tape = useTapeStore.getState();
    if (tape.active) {
      const hit = this.pickScenePoint(event);
      if (hit?.nodeId && (hit.nodeId.startsWith('tape-') || hit.nodeId === 'draft')) {
        const end = this.readTapeEnd(event);
        if (end && hit.nodeId.startsWith('tape-')) {
          tape.setDragging({ measureId: hit.nodeId, end });
          this.controls.enabled = false;
        }
      }
    }
  };

  private onPointerMove = (event: PointerEvent): void => {
    const tape = useTapeStore.getState();
    const hit = this.pickScenePoint(event);
    if (tape.dragging && hit) {
      tape.updateEnd(tape.dragging.measureId, tape.dragging.end, hit.point);
      return;
    }
    if (tape.active && tape.draft && hit) {
      tape.setHover(hit.point);
      this.hoverPoint = hit.point;
    }
  };

  private onPointerUp = (event: PointerEvent): void => {
    const tape = useTapeStore.getState();
    if (tape.dragging) {
      tape.setDragging(null);
      this.controls.enabled = true;
      this.pointerDown = null;
      return;
    }
    if (!this.pointerDown) {
      return;
    }
    const dx = event.clientX - this.pointerDown.x;
    const dy = event.clientY - this.pointerDown.y;
    this.pointerDown = null;
    if (dx * dx + dy * dy > CLICK_SLOP_PX * CLICK_SLOP_PX) {
      return;
    }
    if (useEditingStore.getState().dragging) {
      return;
    }
    const hit = this.pickScenePoint(event);
    if (tape.active) {
      if (!hit) {
        return;
      }
      if (!tape.draft) {
        tape.beginDraft(hit.point);
      } else {
        tape.completeDraft(hit.point);
      }
      return;
    }
    const overlayDraft = useOverlayStore.getState().draft;
    if (overlayDraft.placementMode) {
      if (!hit) {
        return;
      }
      const rotation = rotationFromNormal(hit.normal ?? { x: 0, y: 1, z: 0 });
      this.placeOverlayFromDraft(hit.point, rotation);
      return;
    }
    this.selectNode(hit?.nodeId ?? null);
  };

  private readTapeEnd(event: PointerEvent): 'a' | 'b' | null {
    const ndc = pointerToNdc(event, this.canvas);
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(new THREE.Vector2(ndc.x, ndc.y), this.camera);
    const hits = raycaster.intersectObject(this.tapeVisuals.group, true);
    const end = hits[0]?.object.userData['gsTapeEnd'];
    return end === 'a' || end === 'b' ? end : null;
  }

  private onKeyDown = (event: KeyboardEvent): void => {
    const target = event.target;
    if (
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement
    ) {
      return;
    }
    const ctrl = event.ctrlKey || event.metaKey;
    if (ctrl && event.key.toLowerCase() === 'z') {
      event.preventDefault();
      if (event.shiftKey) {
        this.redo();
      } else {
        this.undo();
      }
      return;
    }
    if (ctrl && event.key.toLowerCase() === 'y') {
      event.preventDefault();
      this.redo();
      return;
    }
    if (event.key.toLowerCase() === 't' && !ctrl) {
      event.preventDefault();
      useTapeStore.getState().toggleActive();
      return;
    }
    if (event.key.toLowerCase() === 'w') {
      useEditingStore.getState().setTransformMode('translate');
      this.gizmo?.setMode('translate');
    }
    if (event.key.toLowerCase() === 'e') {
      useEditingStore.getState().setTransformMode('rotate');
      this.gizmo?.setMode('rotate');
    }
    if (event.key.toLowerCase() === 'r') {
      useEditingStore.getState().setTransformMode('scale');
      this.gizmo?.setMode('scale');
    }
  };

  private bindDom(): void {
    this.canvas.addEventListener('pointerdown', this.onPointerDown);
    this.canvas.addEventListener('pointermove', this.onPointerMove);
    this.canvas.addEventListener('pointerup', this.onPointerUp);
    window.addEventListener('keydown', this.onKeyDown);
    this.resizeObserver = new ResizeObserver(() => this.fitRenderer());
    this.resizeObserver.observe(this.canvas.parentElement ?? this.canvas);
  }

  private bindStores(): void {
    this.unsubScene = this.sceneManager.subscribe((state) => {
      useEditingStore.getState().setOutliner(this.sceneManager.getOutliner());
      useEditingStore
        .getState()
        .setHistory(this.sceneManager.canUndo(), this.sceneManager.canRedo());
      useViewerStore.getState().setSceneName(state.name);
      useCalibrationStore.getState().setCalibration(state.calibration, this.extras);
      this.syncRootScale();
      this.tagHosts();
      this.syncSelection();
    });
    this.unsubOverlays = this.overlayManager.subscribe((overlays) => {
      useOverlayStore.getState().setOverlays([...overlays]);
    });
    this.unsubTape = useTapeStore.subscribe((state) => {
      this.tapeVisuals.sync(state.measures, state.draft, state.hover ?? this.hoverPoint);
    });
    this.unsubEditing = useEditingStore.subscribe((state, prev) => {
      if (state.transformMode !== prev.transformMode) {
        this.gizmo?.setMode(state.transformMode);
      }
      if (state.transformSpace !== prev.transformSpace) {
        this.gizmo?.setSpace(state.transformSpace);
      }
      if (state.snapEnabled !== prev.snapEnabled || state.selectedNodeId !== prev.selectedNodeId) {
        this.syncGizmoSnap();
        this.syncSelection();
      }
    });
    this.unsubUnits = useCalibrationStore.subscribe((state, prev) => {
      if (state.unitPref !== prev.unitPref) {
        this.syncGizmoSnap();
      }
    });
  }

  private fitRenderer(): void {
    const parent = this.canvas.parentElement ?? this.canvas;
    const width = Math.max(parent.clientWidth, 1);
    const height = Math.max(parent.clientHeight, 1);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.webgl.setSize(width, height, false);
  }

  private startLoop(): void {
    const tick = (now: number): void => {
      if (this.disposed) {
        return;
      }
      const dt = now - this.lastFrame;
      this.lastFrame = now;
      this.fpsFrames += 1;
      this.fpsElapsed += dt;
      if (this.fpsElapsed >= 400) {
        const fps = (this.fpsFrames * 1000) / this.fpsElapsed;
        this.fpsFrames = 0;
        this.fpsElapsed = 0;
        const memory = readHeapMb();
        useViewerStore.getState().setHud({
          fps,
          gaussianCount: this.splatRenderer?.getGaussianCount() ?? 0,
          memoryMb: memory,
        });
      }
      this.controls.update();
      if (this.selectionHelper.visible) {
        this.selectionHelper.update();
      }
      this.webgl.render(this.scene, this.camera);
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }
}

function mountDefaultProxy(root: THREE.Group): void {
  const hidden = new THREE.MeshBasicMaterial({
    color: 0x88aaff,
    transparent: true,
    opacity: 0,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(24, 24), hidden);
  ground.rotation.x = -Math.PI / 2;
  ground.name = 'proxy-ground';
  ground.userData['id'] = 'proxy-ground';
  root.add(ground);

  const wall = new THREE.Mesh(new THREE.PlaneGeometry(24, 8), hidden.clone());
  wall.position.y = 4;
  wall.name = 'proxy-wall';
  wall.userData['id'] = 'proxy-wall';
  root.add(wall);
}

function isHelper(object: THREE.Object3D): boolean {
  return (
    object.name === 'tape-visuals' ||
    object.parent?.name === 'tape-visuals' ||
    object.type === 'GridHelper'
  );
}

function rotationFromNormal(normal: ScenePoint): ScenePoint {
  const n = new THREE.Vector3(normal.x, normal.y, normal.z).normalize();
  const quat = new THREE.Quaternion().setFromUnitVectors(
    new THREE.Vector3(0, 0, -1),
    n.clone().negate(),
  );
  const euler = new THREE.Euler().setFromQuaternion(quat, 'XYZ');
  return { x: euler.x, y: euler.y, z: euler.z };
}

function buildOverlayDraft(
  draft: {
    kind: OverlayDraft['kind'];
    imageUrl: string | null;
    color: string;
    opacity: number;
    blendMode: OverlayDraft['blendMode'];
    width: number;
    height: number;
    sizeUnit: 'mm' | 'cm' | 'm' | 'in' | 'ft';
    maskEnabled: boolean;
  },
  point: ScenePoint,
  rotation: ScenePoint,
): OverlayDraft {
  const physicalSize = {
    width: { value: draft.width, unit: draft.sizeUnit },
    height: { value: draft.height, unit: draft.sizeUnit },
  };
  const transform = {
    position: point,
    rotation,
    scale: { x: 1, y: 1, z: 0.5 },
  };
  const maskByNormal = { enabled: draft.maskEnabled, threshold: 0.5 };
  switch (draft.kind) {
    case 'paint':
      return {
        kind: 'paint',
        color: draft.color,
        opacity: draft.opacity,
        blendMode: draft.blendMode,
        physicalSize,
        transform,
        maskByNormal,
        textureRef: draft.imageUrl ?? undefined,
      };
    case 'wallpaper':
      return {
        kind: 'wallpaper',
        textureRef: draft.imageUrl ?? '',
        opacity: draft.opacity,
        blendMode: draft.blendMode,
        physicalSize,
        transform,
        maskByNormal,
      };
    case 'sticker':
      return {
        kind: 'sticker',
        textureRef: draft.imageUrl ?? '',
        opacity: draft.opacity,
        blendMode: draft.blendMode,
        physicalSize,
        transform,
        maskByNormal,
      };
    default: {
      const exhaustive: never = draft.kind;
      return exhaustive;
    }
  }
}

function readHeapMb(): number | null {
  const perf = performance as Performance & { memory?: { usedJSHeapSize: number } };
  if (!perf.memory) {
    return null;
  }
  return perf.memory.usedJSHeapSize / (1024 * 1024);
}

function isProxyMesh(object: THREE.Object3D): boolean {
  return object.name.startsWith('proxy-') || object.parent?.name === 'proxy-root';
}
