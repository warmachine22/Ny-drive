import './styles.css';
import { KeyboardInput } from './input/KeyboardInput';
import { FixedStepRunner } from './physics/FixedStep';
import { createPhysicsRuntime } from './physics/PhysicsWorld';
import { createRenderScene } from './render/createScene';
import { RaycastVehicle } from './vehicle/RaycastVehicle';
import { FloatingOrigin } from './world/FloatingOrigin';
import { ThreeTileRuntimeAdapter } from './world/ThreeTileRuntimeAdapter';
import { WorldStreamer } from './world/WorldStreamer';
import { HttpWorldSource } from './world/WorldSource';

const FIXED_DELTA_SECONDS = 1 / 120;

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

  const worldCenter = streamer.worldCenter();
  const provisionalOrigin = new FloatingOrigin(worldCenter, 512);
  await streamer.update(worldCenter, provisionalOrigin.origin);
  const spawn = streamer.nearestLoadedRoadPoint(worldCenter) ?? worldCenter;

  const spawnOriginShift = provisionalOrigin.setOrigin(spawn);
  streamer.rebase(spawnOriginShift);
  await streamer.update(spawn, provisionalOrigin.origin);

  // T006 established that Rapier world-level scene queries observe newly inserted or
  // translated standalone road colliders after the normal world update path runs.
  // Refresh once before the vehicle begins issuing suspension rays.
  physics.step(FIXED_DELTA_SECONDS);

  const floatingOrigin = provisionalOrigin;
  const vehicle = new RaycastVehicle(physics, { x: 0, z: 0 });
  const fixedStep = new FixedStepRunner(FIXED_DELTA_SECONDS, 8);
  vehicle.syncVisual(render.playerCar);
  input.attach();

  const resize = (): void => render.resize(app.clientWidth, app.clientHeight);
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(app);
  resize();

  let frame = 0;
  let previous = performance.now();
  let streamUpdate: Promise<void> | null = null;
  let streamError: Error | null = null;
  let droppedSimulationSeconds = 0;

  const vehicleGlobalPosition = (): { x: number; y: number } => {
    const local = vehicle.localPosition();
    return floatingOrigin.globalFromLocal({ x: local.x, z: local.z });
  };

  const requestStreamUpdate = (): void => {
    if (streamUpdate) return;
    streamUpdate = streamer
      .update(vehicleGlobalPosition(), floatingOrigin.origin)
      .catch((error: unknown) => {
        streamError = error instanceof Error ? error : new Error(String(error));
      })
      .finally(() => {
        streamUpdate = null;
      });
  };

  const refreshRapierQueries = (): void => {
    vehicle.clearForces();
    physics.step(FIXED_DELTA_SECONDS);
    fixedStep.reset();
  };

  const resetToSpawn = (): void => {
    const local = vehicle.localPosition();
    const currentGlobal = floatingOrigin.globalFromLocal({ x: local.x, z: local.z });
    const shift = floatingOrigin.setOrigin(spawn);
    if (shift.x !== 0 || shift.y !== 0) {
      streamer.rebase(shift);
      vehicle.rebase(shift);
    }
    vehicle.reset({ x: 0, z: 0 });
    droppedSimulationSeconds = 0;
    refreshRapierQueries();
    void streamer.update(spawn, floatingOrigin.origin).catch((error: unknown) => {
      streamError = error instanceof Error ? error : new Error(String(error));
    });
    // Keep this read here deliberately: it makes reset geography explicit in the
    // runtime and guards against accidentally treating local (0,0) as NYC-global.
    void currentGlobal;
  };

  const tick = (now: number): void => {
    const frameDelta = Math.min(Math.max((now - previous) / 1000, 0), 0.1);
    previous = now;

    const controls = input.state.snapshot();
    if (controls.reset) resetToSpawn();

    const localBeforeRebase = vehicle.localPosition();
    const rebase = floatingOrigin.rebaseIfNeeded({
      x: localBeforeRebase.x,
      z: localBeforeRebase.z,
    });
    if (rebase) {
      // Move dynamic and static physics by the exact same floating-origin delta.
      // One fixed refresh step makes the translated road colliders visible to the
      // next world-level suspension query before force application resumes.
      vehicle.rebase(rebase.shift);
      streamer.rebase(rebase.shift);
      refreshRapierQueries();
    }

    const playerGlobal = vehicleGlobalPosition();
    const worldReady = streamer.isPhysicsReadyAt(playerGlobal);
    if (worldReady) {
      const result = fixedStep.advance(frameDelta, (deltaSeconds) => {
        vehicle.preStep(controls, deltaSeconds);
        physics.step(deltaSeconds);
      });
      droppedSimulationSeconds += result.droppedSeconds;
    } else {
      vehicle.clearForces();
      fixedStep.reset();
    }

    vehicle.syncVisual(render.playerCar);
    requestStreamUpdate();
    render.renderer.render(render.scene, render.camera);

    const debug = streamer.debugSnapshot();
    const telemetry = vehicle.telemetry();
    const origin = floatingOrigin.origin;
    const speedKph = telemetry.speedMps * 3.6;
    const slipDegrees = (telemetry.maxAbsSlipAngleRad * 180) / Math.PI;
    status?.replaceChildren(
      streamError
        ? `World streaming failed: ${streamError.message}`
        : `${speedKph.toFixed(0)} km/h · wheels ${telemetry.contactCount}/4 · slip ${slipDegrees.toFixed(1)}° · tiles ${debug.activePhysicsTiles} physics / ${debug.renderedTiles} rendered / ${debug.loadedTiles} cached · colliders ${debug.colliderCount} · origin ${origin.x.toFixed(0)}, ${origin.y.toFixed(0)} m${worldReady ? '' : ' · loading road tile…'}${droppedSimulationSeconds > 0 ? ` · dropped ${(droppedSimulationSeconds * 1000).toFixed(0)} ms sim` : ''}`,
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
      vehicle.dispose();
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
