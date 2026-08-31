import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { DEFAULT_ISOMETRIC_CAMERA, IsometricFollowCamera } from './IsometricFollowCamera';

describe('IsometricFollowCamera', () => {
  it('uses the wide elevated Manhattan-grid presentation chosen after owner playtest', () => {
    expect(THREE.MathUtils.radToDeg(DEFAULT_ISOMETRIC_CAMERA.yawRad)).toBeCloseTo(105, 6);
    expect(THREE.MathUtils.radToDeg(DEFAULT_ISOMETRIC_CAMERA.pitchRad)).toBeCloseTo(58, 6);
    expect(DEFAULT_ISOMETRIC_CAMERA.distanceM).toBe(52);
    expect(DEFAULT_ISOMETRIC_CAMERA.maxLookAheadM).toBe(20);
    expect(DEFAULT_ISOMETRIC_CAMERA.highSpeedZoom).toBeLessThan(0.75);
  });

  it('smooths target movement instead of snapping to a new vehicle pose', () => {
    const camera = new THREE.OrthographicCamera(-10, 10, 10, -10, 0.1, 200);
    const controller = new IsometricFollowCamera(camera);
    controller.reset({
      position: { x: 0, y: 1, z: 0 },
      velocity: { x: 0, y: 0, z: 0 },
    });

    controller.update(
      {
        position: { x: 100, y: 1, z: 0 },
        velocity: { x: 0, y: 0, z: 0 },
      },
      1 / 60,
    );

    const state = controller.debugState();
    expect(state.focus.x).toBeGreaterThan(0);
    expect(state.focus.x).toBeLessThan(100);
  });

  it('keeps a fixed world-isometric offset and clamps speed look-ahead', () => {
    const camera = new THREE.OrthographicCamera(-10, 10, 10, -10, 0.1, 200);
    const controller = new IsometricFollowCamera(camera);
    controller.reset({
      position: { x: 20, y: 1, z: 30 },
      velocity: { x: 100, y: 12, z: -100 },
    });

    const state = controller.debugState();
    expect(Math.hypot(state.lookAhead.x, state.lookAhead.z)).toBeLessThanOrEqual(20.0001);
    expect(state.lookAhead.y).toBe(0);

    const target = new THREE.Vector3(
      state.focus.x + state.lookAhead.x,
      state.focus.y + state.lookAhead.y,
      state.focus.z + state.lookAhead.z,
    );
    const offset = camera.position.clone().sub(target);
    expect(offset.y).toBeGreaterThan(0);
    expect(offset.length()).toBeCloseTo(52, 5);
  });

  it('rebases camera state by the same local shift without a visual jump', () => {
    const camera = new THREE.OrthographicCamera(-10, 10, 10, -10, 0.1, 200);
    const controller = new IsometricFollowCamera(camera);
    controller.reset({
      position: { x: 520, y: 1, z: -260 },
      velocity: { x: 0, y: 0, z: 0 },
    });
    const beforeCamera = camera.position.clone();
    const beforeFocus = controller.debugState().focus;

    controller.rebase({ x: 512, y: -256 });

    const afterFocus = controller.debugState().focus;
    expect(afterFocus.x).toBeCloseTo(beforeFocus.x - 512);
    expect(afterFocus.z).toBeCloseTo(beforeFocus.z + 256);
    expect(camera.position.x).toBeCloseTo(beforeCamera.x - 512);
    expect(camera.position.z).toBeCloseTo(beforeCamera.z + 256);
  });

  it('zooms out materially at speed without depending on chassis yaw/roll', () => {
    const camera = new THREE.OrthographicCamera(-10, 10, 10, -10, 0.1, 200);
    const controller = new IsometricFollowCamera(camera);
    controller.reset({
      position: { x: 0, y: 0, z: 0 },
      velocity: { x: 0, y: 0, z: 0 },
    });
    const idleZoom = controller.debugState().zoom;

    for (let index = 0; index < 30; index += 1) {
      controller.update(
        {
          position: { x: 0, y: 0, z: -index },
          velocity: { x: 0, y: 0, z: -40 },
        },
        1 / 60,
      );
    }

    expect(controller.debugState().zoom).toBeLessThan(idleZoom);
    expect(controller.debugState().zoom).toBeGreaterThanOrEqual(0.71);
  });
});
