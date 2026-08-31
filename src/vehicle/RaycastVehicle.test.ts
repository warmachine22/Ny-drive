import RAPIER from '@dimforge/rapier3d-compat';
import { describe, expect, it } from 'vitest';
import { createPhysicsRuntime } from '../physics/PhysicsWorld';
import { RaycastVehicle } from './RaycastVehicle';

const neutralInput = {
  steer: 0,
  throttle: 0,
  brakeReverse: 0,
  handbrake: false,
  reset: false,
};

describe('RaycastVehicle', () => {
  it('uses a dynamic chassis and excludes itself from suspension queries', async () => {
    const physics = await createPhysicsRuntime();
    const vehicle = new RaycastVehicle(physics);
    physics.step(1 / 120);
    vehicle.preStep(neutralInput, 1 / 120);

    expect(vehicle.body.isDynamic()).toBe(true);
    expect(vehicle.telemetry().contactCount).toBe(0);

    vehicle.dispose();
    physics.dispose();
  });

  it('settles four suspension contacts and accelerates through tire forces on a road plane', async () => {
    const physics = await createPhysicsRuntime();
    physics.world.createCollider(
      RAPIER.ColliderDesc.cuboid(30, 0.1, 30)
        .setTranslation(0, -0.1, 0)
        .setFriction(1.05),
    );
    physics.step(1 / 120);

    const vehicle = new RaycastVehicle(physics);
    for (let step = 0; step < 360; step += 1) {
      vehicle.preStep(
        {
          ...neutralInput,
          throttle: step > 120 ? 1 : 0,
        },
        1 / 120,
      );
      physics.step(1 / 120);
    }

    const telemetry = vehicle.telemetry();
    const position = vehicle.localPosition();
    expect(telemetry.contactCount).toBeGreaterThanOrEqual(3);
    expect(telemetry.speedMps).toBeGreaterThan(1);
    expect(position.y).toBeGreaterThan(0.35);
    expect(position.y).toBeLessThan(1.2);
    expect(Number.isFinite(telemetry.maxAbsSlipAngleRad)).toBe(true);

    vehicle.dispose();
    physics.dispose();
  });
});
