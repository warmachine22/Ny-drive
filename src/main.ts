import './styles.css';
import { KeyboardInput } from './input/KeyboardInput';
import { createPhysicsRuntime } from './physics/PhysicsWorld';
import { createRenderScene } from './render/createScene';
import { FloatingOrigin } from './world/FloatingOrigin';
import { ThreeTileRuntimeAdapter } from './world/ThreeTileRuntimeAdapter';
import { WorldStreamer } from './world/WorldStreamer';
import { HttpWorldSource } from './world/WorldSource';

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
  <div class="hud__status" role="status" aria-live="polite">Initializing physics and world…</div>
  <div class="hud__controls">WASD / arrows · Space handbrake · R reset</div>
`;
app.append(hud);

const status = hud.querySelector<HTMLElement>('.hud__status');

async function boot(): Promise<void> {
  const render = createRenderScene(canvas);
  const physics = await createPhysicsRuntime();
  const input = new KeyboardInput();
  const tileAdapter = new ThreeTileRuntimeAdapter(render.scene, physics);
  const streamer = new WorldStreamer(new HttpWorldSource('/manifest.json'), tileAdapter);
  await streamer.initialize();
  const spawn = streamer.worldCenter();
  const floatingOrigin = new FloatingOrigin(spawn, 512);
  await streamer.update(spawn, floatingOrigin.origin);
  input.attach();

  const resize = (): void => render.resize(app.clientWidth, app.clientHeight);
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(app);
  resize();

  let frame = 0;
  let previous = performance.now();
  let streamUpdate: Promise<void> | null = null;
  let streamError: Error | null = null;

  const requestStreamUpdate = (): void => {
    if (streamUpdate) return;
    const global = floatingOrigin.globalFromLocal({
      x: render.placeholderCar.position.x,
      z: render.placeholderCar.position.z,
    });
    streamUpdate = streamer
      .update(global, floatingOrigin.origin)
      .catch((error: unknown) => {
        streamError = error instanceof Error ? error : new Error(String(error));
      })
      .finally(() => {
        streamUpdate = null;
      });
  };

  const resetToSpawn = (): void => {
    const shift = floatingOrigin.setOrigin(spawn);
    streamer.rebase(shift);
    render.placeholderCar.position.set(0, 0.5, 0);
    render.placeholderCar.rotation.set(0, 0, 0);
  };

  const tick = (now: number): void => {
    const delta = Math.min((now - previous) / 1000, 0.05);
    previous = now;

    const controls = input.state.snapshot();
    const playerBeforeMove = floatingOrigin.globalFromLocal({
      x: render.placeholderCar.position.x,
      z: render.placeholderCar.position.z,
    });
    const worldReady = streamer.isPhysicsReadyAt(playerBeforeMove);
    if (worldReady) {
      render.placeholderCar.rotation.y += controls.steer * delta * 1.8;
      render.placeholderCar.position.z -= (controls.throttle - controls.brakeReverse) * delta * 5;
      render.placeholderCar.rotation.z = controls.handbrake ? -0.06 : 0;
    }
    if (controls.reset) resetToSpawn();

    const rebase = floatingOrigin.rebaseIfNeeded({
      x: render.placeholderCar.position.x,
      z: render.placeholderCar.position.z,
    });
    if (rebase) {
      render.placeholderCar.position.x = rebase.local.x;
      render.placeholderCar.position.z = rebase.local.z;
      streamer.rebase(rebase.shift);
    }

    requestStreamUpdate();
    physics.step(delta || 1 / 60);
    render.renderer.render(render.scene, render.camera);

    const debug = streamer.debugSnapshot();
    const origin = floatingOrigin.origin;
    status?.replaceChildren(
      streamError
        ? `World streaming failed: ${streamError.message}`
        : `tiles ${debug.activePhysicsTiles} physics / ${debug.renderedTiles} rendered / ${debug.loadedTiles} cached · colliders ${debug.colliderCount} · origin ${origin.x.toFixed(0)}, ${origin.y.toFixed(0)} m${worldReady ? '' : ' · loading road tile…'}`,
    );
    frame = requestAnimationFrame(tick);
  };
  frame = requestAnimationFrame(tick);

  window.addEventListener(
    'pagehide',
    () => {
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      input.detach();
      void streamer.dispose();
      tileAdapter.dispose();
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
