import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

/** Carrega um GLB local no host da cena e devolve a object URL usada como `uri`. */
export async function loadGlbIntoHost(file: File, host: THREE.Object3D): Promise<string> {
  const url = URL.createObjectURL(file);
  const loader = new GLTFLoader();
  try {
    const gltf = await loader.loadAsync(url);
    gltf.scene.traverse((child) => {
      child.userData['gsNodeId'] = host.userData['gsNodeId'];
    });
    host.add(gltf.scene);
    return url;
  } catch (error) {
    URL.revokeObjectURL(url);
    throw error;
  }
}

export function nodeNameFromFile(file: File): string {
  return file.name.replace(/\.(glb|gltf)$/i, '') || 'Objeto';
}
