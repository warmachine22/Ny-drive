import RAPIER from '@dimforge/rapier3d-compat';
import { describe, expect, it } from 'vitest';
import { createPhysicsRuntime } from '../physics/PhysicsWorld';
import {
  RoadCollisionManager,
  buildRoadCollisionMesh,
  buildRoadSurfaceCollisionMesh,
} from './RoadCollision';
import type { TilePayload } from './types';

function squareTile(id = '0:0', origin: [number, number] = [0, 0]): TilePayload {
  return {
    schema_version: 1,
    tile_id: id,
    index: [0, 0],
    origin_m: origin,
    size_m: 256,
    road_surfaces: [
      {
        stable_id: 'roadbed:square',
        source_id: 'square',
        source_key: 'roadbed',
        feature_code: 3500,
        sub_code: null,
        status: 'active',
        polygons: [
          {
            outer: [[0, 0], [20, 0], [20, 20], [0, 20], [0, 0]],
            holes: [],
          },
        ],
      },
    ],
    roads: [],
  };
}

describe('road collision geometry', () => {
  it('triangulates compiled roadbed surfaces rather than centerline ribbons', () => {
    const tile = squareTile();
    tile.roads.push({
      stable_id: 'centerline:1',
      source_id: '1',
      source_key: 'centerline',
      name: 'TEST STREET',
      directionality: 'both',
      lanes: 2,
      lanes_forward: null,
      lanes_backward: null,
      width_m: 12,
      road_class: 'street',
      bridge: false,
      tunnel: false,
      layer: 0,
      from_level_code: null,
      to_level_code: null,
      paths: [[[0, 10], [20, 10]]],
    });
    const mesh = buildRoadCollisionMesh(tile);
    expect(mesh.triangleCount).toBe(2);
    expect(mesh.vertices.length).toBe(18);
  });

  it('uses compiled per-vertex elevation for schema-v2 Roadbed collision', () => {
    const tile = squareTile();
    tile.schema_version = 2;
    tile.road_surfaces[0]!.vertical_status = 'resolved';
    tile.road_surfaces[0]!.polygons[0]!.outer = [
      [0, 0, 3],
      [20, 0, 3],
      [20, 20, 5],
      [0, 20, 5],
      [0, 0, 3],
    ];
    const mesh = buildRoadCollisionMesh(tile);
    const elevations = [];
    for (let index = 1; index < mesh.vertices.length; index += 3) {
      elevations.push(mesh.vertices[index]);
    }
    expect(Math.min(...elevations)).toBe(3);
    expect(Math.max(...elevations)).toBe(5);
  });

  it('omits unresolved vertical Roadbed rather than creating a false crossing', () => {
    const surface = squareTile().road_surfaces[0]!;
    surface.vertical_status = 'unresolved';
    expect(buildRoadSurfaceCollisionMesh(surface).triangleCount).toBe(0);
  });

  it('creates one static trimesh per active tile, supports ray contact, rebases, and removes it cleanly', async () => {
    const physics = await createPhysicsRuntime();
    const collisions = new RoadCollisionManager(physics.world);
    const tile = squareTile('5:12', [1280, 3072]);
    const origin = { x: 1280, y: 3072 };

    expect(collisions.activateTile(tile, origin)).toBe(1);
    expect(collisions.activateTile(tile, origin)).toBe(1);
    expect(collisions.colliderCount()).toBe(1);
    expect(physics.world.colliders.len()).toBe(1);

    const ray = new RAPIER.Ray({ x: 10, y: 3, z: 10 }, { x: 0, y: -1, z: 0 });
    const collider = physics.world.colliders.getAll()[0];
    expect(collider).toBeDefined();
    expect(collider?.castRay(ray, 10, true)).toBeGreaterThanOrEqual(0);

    // World-level scene queries use Rapier's query acceleration structure,
    // which is refreshed by the normal simulation step.
    physics.step(1 / 60);
    expect(physics.world.castRay(ray, 10, true)).not.toBeNull();

    collisions.rebase({ x: 5, y: 7 });
    expect(collider?.translation().x).toBeCloseTo(-5);
    expect(collider?.translation().z).toBeCloseTo(-7);

    collisions.deactivateTile(tile.tile_id);
    expect(collisions.colliderCount()).toBe(0);
    expect(physics.world.colliders.len()).toBe(0);
    physics.dispose();
  });
});
