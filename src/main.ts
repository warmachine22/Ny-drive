import './styles.css';
import { KeyboardInput } from './input/KeyboardInput';
import { createPhysicsRuntime } from './physics/PhysicsWorld';
import { createRenderScene } from './render/createScene';

function requireAppRoot(): HTMLElement {
  const root = document.querySelector<HTMLElement>('#app');
  if (!root) throw new Error('Missing #app root.');
  return root;
}

const app = requireAppRoot();

const canvas = document.createElement('canvas');
canvas.className = 'game-canvas';
canvas.setAttribute('aria-label', 'Ny-drive 3D viewport');
app.append(canvas);

const hud = document.createElement('section');
hud.className = 'hud';
hud.innerHTML = `
  <div class="hud__brand">NY-DRIVE <span>prototype</span></div>
  <div class="hud__status" role="status" aria-live="polite">Initializing physics…</div>
  <div class="hud__controls">WASD / arrows · Space handbrake · R reset</div>
`;
app.append(hud);

const status = hud.querySelector<HTMLElement>('.hud__status');

async function boot(): Promise<void> {
  const render = createRenderScene(canvas);
  const physics = await createPhysicsRuntime();
  const input = new KeyboardInput();
  input.attach();

  status?.replaceChildren('Three.js + Rapier ready');

  const resize = (): void => render.resize(app.clientWidth, app.clientHeight);
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(app);
  resize();

  let frame = 0;
  let previous = performance.now();
  const tick = (now: number): void => {
    const delta = Math.min((now - previous) / 1000, 0.05);
    previous = now;

    const controls = input.state.snapshot();
    render.placeholderCar.rotation.y += controls.steer * delta * 1.8;
    render.placeholderCar.position.z -= (controls.throttle - controls.brakeReverse) * delta * 5;
    render.placeholderCar.rotation.z = controls.handbrake ? -0.06 : 0;
    if (controls.reset) {
      render.placeholderCar.position.set(0, 0.5, 0);
      render.placeholderCar.rotation.set(0, 0, 0);
    }

    physics.step(delta || 1 / 60);
    render.renderer.render(render.scene, render.camera);
    frame = requestAnimationFrame(tick);
  };
  frame = requestAnimationFrame(tick);

  window.addEventListener(
    'pagehide',
    () => {
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      input.detach();
      physics.dispose();
      render.dispose();
    },
    { once: true },
  );
}

boot().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  status?.replaceChildren(`Startup failed: ${message}`);
  console.error(error);
});
