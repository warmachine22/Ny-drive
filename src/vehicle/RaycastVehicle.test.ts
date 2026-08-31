import RAPIER from '@dimforge/rapier3d-compat';
import { describe, expect, it } from 'vitest';
import { createPhysicsRuntime } from '../physics/PhysicsWorld';
import { RoadCollisionManager } from '../world/RoadCollision';
import type { TilePayload } from '../world/types';
import { RaycastVehicle } from './RaycastVehicle';

const neutralInput = {
  steer: 0,
  throttle: 0,
  brakeReverse: 0,
  handbrake: false,
  reset: false,
};

function seamRoadTile(id: string, originZ: number): TilePayload {
  return {
    schema_version: 1,
    tile_id: id,
    index: [0, Math.floor(originZ / 256)],
    origin_m: [0, originZ],
    size_m: 256,
    road_surfaces: [
      {
        stable_id: `roadbed:${id}`,
        source_id: id,
        source_key: 'test-roadbed',
        feature_code: 3500,
        sub_code: null,
        status: 'active',
        polygons: [
          {
            outer: [[0, 0], [40, 0], [40, 256], [0, 256], [0, 0]],
            holes: [],
          },
        ],
      },
    ],
    roads: [],
  };
}

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

  it('crosses a boundary between adjacent Roadbed tile colliders without losing the road', async () => {
    const physics = await createPhysicsRuntime();
    const collisions = new RoadCollisionManager(physics.world);
    const origin = { x: 0, y: 0 };
    expect(collisions.activateTile(seamRoadTile('0:0', 0), origin)).toBe(1);
    expect(collisions.activateTile(seamRoadTile('0:-1', -256), origin)).toBe(1);
    expect(collisions.colliderCount()).toBe(2);
    physics.step(1 / 120);

    const vehicle = new RaycastVehicle(physics, { x: 20, z: 12 });
    let minimumContacts = 4;
    for (let step = 0; step < 900; step += 1) {
      vehicle.preStep(
        {
          ...neutralInput,
          throttle: step > 120 ? 0.75 : 0,
        },
        1 / 120,
      );
      physics.step(1 / 120);
      if (step > 120) minimumContacts = Math.min(minimumContacts, vehicle.telemetry().contactCount);
    }

    const position = vehicle.localPosition();
    expect(position.z).toBeLessThan(-5);
    expect(position.y).toBeGreaterThan(0.3);
    expect(minimumContacts).toBeGreaterThanOrEqual(3);
    expect(vehicle.telemetry().contactCount).toBeGreaterThanOrEqual(3);

    vehicle.dispose();
    collisions.dispose();
    physics.dispose();
  });
});
