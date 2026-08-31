import RAPIER from '@dimforge/rapier3d-compat';
import { describe, expect, it } from 'vitest';
import { createPhysicsRuntime } from '../physics/PhysicsWorld';
import { RaycastVehicle } from './RaycastVehicle';

const neutral = {
  steer: 0,
  throttle: 0,
  brakeReverse: 0,
  handbrake: false,
  reset: false,
};

describe('normal cornering response', () => {
  it('turns decisively at an ordinary city entry speed without requiring the handbrake', async () => {
    const physics = await createPhysicsRuntime();
    physics.world.createCollider(
      RAPIER.ColliderDesc.cuboid(100, 0.1, 100)
        .setTranslation(0, -0.1, 0)
        .setFriction(1.1),
    );
    physics.step(1 / 120);

    const vehicle = new RaycastVehicle(physics);
    for (let step = 0; step < 180; step += 1) {
      vehicle.preStep(neutral, 1 / 120);
      physics.step(1 / 120);
    }

    // Roughly 49 km/h: fast enough to expose the original prototype understeer,
    // but still a plausible approach speed for a wide Manhattan intersection.
    vehicle.body.setLinvel({ x: 0, y: 0, z: -13.5 }, true);
    let peakYawRate = 0;
    for (let step = 0; step < 180; step += 1) {
      vehicle.preStep(
        {
          ...neutral,
          steer: 0.75,
          throttle: 0.18,
        },
        1 / 120,
      );
      physics.step(1 / 120);
      peakYawRate = Math.max(peakYawRate, Math.abs(vehicle.telemetry().yawRateRadPerSec));
    }

    const position = vehicle.localPosition();
    expect(peakYawRate).toBeGreaterThan(0.3);
    expect(position.x).toBeGreaterThan(1.5);
    expect(vehicle.telemetry().contactCount).toBeGreaterThanOrEqual(3);

    vehicle.dispose();
    physics.dispose();
  });
});
