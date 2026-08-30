import * as THREE from 'three';

export interface RenderScene {
  readonly scene: THREE.Scene;
  readonly camera: THREE.OrthographicCamera;
  readonly renderer: THREE.WebGLRenderer;
  readonly placeholderCar: THREE.Mesh;
  resize(width: number, height: number): void;
  dispose(): void;
}

const VIEW_HEIGHT = 34;

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

  const camera = new THREE.OrthographicCamera(-20, 20, 17, -17, 0.1, 500);
  camera.position.set(24, 28, 24);
  camera.lookAt(0, 0, 0);

  scene.add(new THREE.HemisphereLight(0xdcecff, 0x18202c, 2.2));
  const sun = new THREE.DirectionalLight(0xffffff, 2.8);
  sun.position.set(12, 24, 8);
  scene.add(sun);

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(120, 120),
    new THREE.MeshStandardMaterial({ color: 0x1f2933, roughness: 0.95 }),
  );
  ground.rotation.x = -Math.PI / 2;
  scene.add(ground);

  const grid = new THREE.GridHelper(120, 60, 0x6a7887, 0x34404c);
  grid.position.y = 0.015;
  scene.add(grid);

  const placeholderCar = new THREE.Mesh(
    new THREE.BoxGeometry(1.75, 0.7, 4.35),
    new THREE.MeshStandardMaterial({ color: 0xd8dde4, roughness: 0.55, metalness: 0.15 }),
  );
  placeholderCar.position.y = 0.5;
  scene.add(placeholderCar);

  const resize = (width: number, height: number): void => {
    const safeHeight = Math.max(height, 1);
    const aspect = Math.max(width, 1) / safeHeight;
    const halfHeight = VIEW_HEIGHT / 2;
    camera.left = -halfHeight * aspect;
    camera.right = halfHeight * aspect;
    camera.top = halfHeight;
    camera.bottom = -halfHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(Math.max(width, 1), safeHeight, false);
  };

  const dispose = (): void => {
    ground.geometry.dispose();
    (ground.material as THREE.Material).dispose();
    placeholderCar.geometry.dispose();
    (placeholderCar.material as THREE.Material).dispose();
    renderer.dispose();
  };

  return { scene, camera, renderer, placeholderCar, resize, dispose };
}
