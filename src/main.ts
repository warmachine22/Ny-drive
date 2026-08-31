import './styles.css';
import { IsometricFollowCamera } from './camera/IsometricFollowCamera';
import { FallRecoveryMonitor } from './game/FallRecovery';
import { KeyboardInput } from './input/KeyboardInput';
import { FixedStepRunner } from './physics/FixedStep';
import { createPhysicsRuntime } from './physics/PhysicsWorld';
import { createRenderScene } from './render/createScene';
import { RaycastVehicle } from './vehicle/RaycastVehicle';
import type { RoadPose } from './world/RoadPose';
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
  const spawnPose: RoadPose = streamer.nearestLoadedRoadPose(worldCenter) ?? {
    position: worldCenter,
    headingRad: 0,
    source: 'roadbed',
    roadName: null,
    distanceM: 0,
  };

  const spawnOriginShift = provisionalOrigin.setOrigin(spawnPose.position);
  streamer.rebase(spawnOriginShift);
  await streamer.update(spawnPose.position, provisionalOrigin.origin);

  physics.step(FIXED_DELTA_SECONDS);

  const floatingOrigin = provisionalOrigin;
  const vehicle = new RaycastVehicle(physics, { x: 0, z: 0 });
  vehicle.reset({ x: 0, z: 0 }, spawnPose.headingRad);
  const fixedStep = new FixedStepRunner(FIXED_DELTA_SECONDS, 8);
  const fallRecovery = new FallRecoveryMonitor();
  vehicle.syncVisual(render.playerCar);

  const followCamera = new IsometricFollowCamera(render.camera);
  const cameraMotionState = () => {
    const position = vehicle.localPosition();
    const velocity = vehicle.body.linvel();
    return {
      position,
      velocity: { x: velocity.x, y: velocity.y, z: velocity.z },
    };
  };
  followCamera.reset(cameraMotionState());
  input.attach();

  const resize = (): void => render.resize(app.clientWidth, app.clientHeight);
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(app);
  resize();

  let frame = 0;
  let previous = performance.now();
  let streamUpdate: Promise<void> | null = null;
  let resetInFlight: Promise<void> | null = null;
  let resetReason: 'manual' | 'fall' | null = null;
  let streamError: Error | null = null;
  let droppedSimulationSeconds = 0;

  const vehicleGlobalPosition = (): { x: number; y: number } => {
    const local = vehicle.localPosition();
    return floatingOrigin.globalFromLocal({ x: local.x, z: local.z });
  };

  const requestStreamUpdate = (): void => {
    if (streamUpdate || resetInFlight) return;
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

  const performSafeReset = async (): Promise<void> => {
    const pendingStream = streamUpdate;
    if (pendingStream) await pendingStream;

    const currentGlobal = vehicleGlobalPosition();
    await streamer.update(currentGlobal, floatingOrigin.origin);
    const pose = streamer.nearestLoadedRoadPose(currentGlobal) ?? spawnPose;

    const shift = floatingOrigin.setOrigin(pose.position);
    if (shift.x !== 0 || shift.y !== 0) {
      vehicle.rebase(shift);
      streamer.rebase(shift);
      followCamera.rebase(shift);
    }

    await streamer.update(pose.position, floatingOrigin.origin);
    refreshRapierQueries();
    vehicle.reset({ x: 0, z: 0 }, pose.headingRad);
    vehicle.syncVisual(render.playerCar);
    followCamera.reset(cameraMotionState());
    fallRecovery.reset();
    droppedSimulationSeconds = 0;
  };

  const requestReset = (reason: 'manual' | 'fall'): void => {
    if (resetInFlight) return;
    resetReason = reason;
    resetInFlight = performSafeReset()
      .catch((error: unknown) => {
        streamError = error instanceof Error ? error : new Error(String(error));
      })
      .finally(() => {
        resetInFlight = null;
        resetReason = null;
      });
  };

  const tick = (now: number): void => {
    const frameDelta = Math.min(Math.max((now - previous) / 1000, 0), 0.1);
    previous = now;

    const controls = input.state.snapshot();
    if (controls.reset) requestReset('manual');
    if (!resetInFlight && fallRecovery.update(vehicle.localPosition().y)) {
      requestReset('fall');
    }

    if (!resetInFlight) {
      const localBeforeRebase = vehicle.localPosition();
      const rebase = floatingOrigin.rebaseIfNeeded({
        x: localBeforeRebase.x,
        z: localBeforeRebase.z,
      });
      if (rebase) {
        vehicle.rebase(rebase.shift);
        streamer.rebase(rebase.shift);
        followCamera.rebase(rebase.shift);
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
    } else {
      vehicle.clearForces();
      fixedStep.reset();
    }

    vehicle.syncVisual(render.playerCar);
    followCamera.update(cameraMotionState(), frameDelta);
    requestStreamUpdate();
    render.renderer.render(render.scene, render.camera);

    const playerGlobal = vehicleGlobalPosition();
    const worldReady = streamer.isPhysicsReadyAt(playerGlobal);
    const debug = streamer.debugSnapshot();
    const telemetry = vehicle.telemetry();
    const origin = floatingOrigin.origin;
    const speedKph = telemetry.speedMps * 3.6;
    const slipDegrees = (telemetry.maxAbsSlipAngleRad * 180) / Math.PI;
    const rearSlipDegrees = (telemetry.rearMaxAbsSlipAngleRad * 180) / Math.PI;
    const yawRateDegrees = (telemetry.yawRateRadPerSec * 180) / Math.PI;
    const resetLabel =
      resetReason === 'fall'
        ? ' · recovering fall…'
        : resetReason === 'manual'
          ? ' · resetting to road…'
          : '';
    status?.replaceChildren(
      streamError
        ? `World streaming failed: ${streamError.message}`
        : `${speedKph.toFixed(0)} km/h · wheels ${telemetry.contactCount}/4 · slip ${slipDegrees.toFixed(1)}° / rear ${rearSlipDegrees.toFixed(1)}° · yaw ${yawRateDegrees.toFixed(0)}°/s${telemetry.handbrakeActive ? ' · HB' : ''} · tiles ${debug.activePhysicsTiles} physics / ${debug.renderedTiles} rendered / ${debug.loadedTiles} cached · colliders ${debug.colliderCount} · origin ${origin.x.toFixed(0)}, ${origin.y.toFixed(0)} m${resetLabel || (worldReady ? '' : ' · loading road tile…')}${droppedSimulationSeconds > 0 ? ` · dropped ${(droppedSimulationSeconds * 1000).toFixed(0)} ms sim` : ''}`,
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
