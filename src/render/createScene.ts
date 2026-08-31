import * as THREE from 'three';

export interface RenderScene {
  readonly scene: THREE.Scene;
  readonly camera: THREE.OrthographicCamera;
  readonly renderer: THREE.WebGLRenderer;
  readonly playerCar: THREE.Group;
  resize(width: number, height: number): void;
  dispose(): void;
}

// T009 used a 34 m vertical view, which made the 4.3 m car dominate the screen and
// left too little NYC street context to anticipate turns. Browser comparison against
// the owner's Smashy Road reference found 88 m made the prototype car too small, so
// 68 m is the balanced stationary baseline; speed zoom expands that toward ~94 m.
export const BASE_VIEW_HEIGHT_M = 68;

function createPrototypeCar(): {
  group: THREE.Group;
  geometries: THREE.BufferGeometry[];
  materials: THREE.Material[];
} {
  const group = new THREE.Group();
  group.name = 'player-car:unbranded-gc8-era';
  group.userData.vehicleStyle = 'unbranded-gc8-era';

  const bodyMaterial = new THREE.MeshStandardMaterial({
    color: 0xd8dde4,
    roughness: 0.52,
    metalness: 0.18,
  });
  const glassMaterial = new THREE.MeshStandardMaterial({
    color: 0x314457,
    roughness: 0.28,
    metalness: 0.08,
  });
  const trimMaterial = new THREE.MeshStandardMaterial({
    color: 0x151a20,
    roughness: 0.78,
    metalness: 0.05,
  });
  const materials: THREE.Material[] = [bodyMaterial, glassMaterial, trimMaterial];
  const geometries: THREE.BufferGeometry[] = [];

  const addBox = (
    size: [number, number, number],
    position: [number, number, number],
    material: THREE.Material,
  ): THREE.Mesh => {
    const geometry = new THREE.BoxGeometry(...size);
    geometries.push(geometry);
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(...position);
    group.add(mesh);
    return mesh;
  };

  addBox([1.72, 0.52, 4.28], [0, 0, 0], bodyMaterial);
  addBox([1.48, 0.58, 1.95], [0, 0.48, 0.18], glassMaterial);
  addBox([1.58, 0.12, 0.38], [0, 0.55, 1.9], bodyMaterial);
  addBox([1.36, 0.08, 0.16], [0, 0.72, 1.82], trimMaterial);

  const wheelGeometry = new THREE.CylinderGeometry(0.3, 0.3, 0.22, 12);
  geometries.push(wheelGeometry);
  for (const x of [-0.84, 0.84]) {
    for (const z of [-1.26, 1.26]) {
      const wheel = new THREE.Mesh(wheelGeometry, trimMaterial);
      wheel.rotation.z = Math.PI / 2;
      wheel.position.set(x, -0.28, z);
      group.add(wheel);
    }
  }

  return { group, geometries, materials };
}

export function createRenderScene(canvas: HTMLCanvasElement): RenderScene {
  const context = canvas.getContext('webgl2', {
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
  });
  if (!context) {
    throw new Error('Ny-drive requires WebGL2 support.');
  }

  const renderer = new THREE.WebGLRenderer({ canvas, context, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b1017);

  const camera = new THREE.OrthographicCamera(-34, 34, 34, -34, 0.1, 500);
  camera.position.set(24, 28, 24);
  camera.lookAt(0, 0, 0);

  scene.add(new THREE.HemisphereLight(0xdcecff, 0x18202c, 2.2));
  const sun = new THREE.DirectionalLight(0xffffff, 2.8);
  sun.position.set(12, 24, 8);
  scene.add(sun);

  // Ground is intentionally not camera-local. T017 streams a support surface with
  // each eligible world tile so visual/physics lifetime follows the world streamer
  // instead of ending at the old fixed 120 m debug plane.
  const prototype = createPrototypeCar();
  const playerCar = prototype.group;
  scene.add(playerCar);

  const resize = (width: number, height: number): void => {
    const safeHeight = Math.max(height, 1);
    const aspect = Math.max(width, 1) / safeHeight;
    const halfHeight = BASE_VIEW_HEIGHT_M / 2;
    camera.left = -halfHeight * aspect;
    camera.right = halfHeight * aspect;
    camera.top = halfHeight;
    camera.bottom = -halfHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(Math.max(width, 1), safeHeight, false);
  };

  const dispose = (): void => {
    for (const geometry of new Set(prototype.geometries)) geometry.dispose();
    for (const material of new Set(prototype.materials)) material.dispose();
    renderer.dispose();
  };

  return { scene, camera, renderer, playerCar, resize, dispose };
}
