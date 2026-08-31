import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { createPhysicsRuntime } from '../physics/PhysicsWorld';
import { ThreeTileRuntimeAdapter } from './ThreeTileRuntimeAdapter';
import type { TilePayload } from './types';

function tile(): TilePayload {
  return {
    schema_version: 1,
    tile_id: '4:13',
    index: [4, 13],
    origin_m: [1024, 3328],
    size_m: 256,
    road_surfaces: [
      {
        stable_id: 'nyc-planimetrics-roadbed:1',
        source_id: '1',
        source_key: 'nyc-planimetrics-roadbed',
        feature_code: 3500,
        sub_code: 350000,
        status: 'Updated',
        polygons: [{ outer: [[0, 0], [30, 0], [30, 20], [0, 20], [0, 0]], holes: [] }],
      },
    ],
    roads: [
      {
        stable_id: 'nyc-cscl-centerline:7',
        source_id: '7',
        source_key: 'nyc-cscl-centerline',
        name: 'BROADWAY',
        directionality: 'both',
        lanes: 4,
        lanes_forward: null,
        lanes_backward: null,
        width_m: 18,
        road_class: '1',
        bridge: false,
        tunnel: false,
        layer: 0,
        from_level_code: '13',
        to_level_code: '13',
        paths: [[[0, 10], [30, 10]]],
      },
    ],
  };
}

describe('ThreeTileRuntimeAdapter', () => {
  it('streams support below Roadbed and bounds both collider types to physics activation', async () => {
    const scene = new THREE.Scene();
    const physics = await createPhysicsRuntime();
    const adapter = new ThreeTileRuntimeAdapter(scene, physics);
    const fixture = tile();

    adapter.attachTile(fixture, { x: 1024, y: 3328 });
    const group = scene.getObjectByName('world-tile:4:13');
    expect(group).toBeDefined();
    const support = group?.getObjectByName('support-ground:4:13');
    expect(support?.userData.supportGround).toBe(true);
    expect(support?.position.y).toBeLessThan(-0.2);
    const centerline = group?.children.find((child) => child.userData.road?.name === 'BROADWAY');
    expect(centerline?.userData.road).toMatchObject({ lanes: 4, widthM: 18, roadClass: '1' });
    expect(physics.world.colliders.len()).toBe(0);

    expect(adapter.setPhysicsActive(fixture.tile_id, true)).toBe(2);
    expect(physics.world.colliders.len()).toBe(2);
    expect(adapter.setPhysicsActive(fixture.tile_id, true)).toBe(2);
    expect(physics.world.colliders.len()).toBe(2);

    adapter.setPhysicsActive(fixture.tile_id, false);
    expect(physics.world.colliders.len()).toBe(0);
    adapter.dispose();
    physics.dispose();
  });
});
