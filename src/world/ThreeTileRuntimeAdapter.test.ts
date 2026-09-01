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
    buildings: [
      {
        stable_id: 'nyc-building-footprints:1',
        source_id: '1',
        source_key: 'nyc-building-footprints',
        feature_code: 2100,
        bin: '1000001',
        name: null,
        construction_year: 1920,
        height_m: 18,
        height_source: 'nyc-height-roof',
        base_elevation_m: 0,
        base_elevation_source: 'flat-fixture',
        source_ground_elevation_m: 5,
        polygons: [{ outer: [[40, 40], [60, 40], [60, 60], [40, 60], [40, 40]], holes: [] }],
      },
      {
        stable_id: 'nyc-building-footprints:2',
        source_id: '2',
        source_key: 'nyc-building-footprints',
        feature_code: 2100,
        bin: '1000002',
        name: null,
        construction_year: null,
        height_m: 12,
        height_source: 'deterministic-visual-fallback',
        base_elevation_m: 0,
        base_elevation_source: 'flat-fixture',
        source_ground_elevation_m: null,
        polygons: [{ outer: [[70, 40], [90, 40], [90, 60], [70, 60], [70, 40]], holes: [] }],
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
  it('batches building massing while bounding physics to driving surfaces', async () => {
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

    const massing = group?.getObjectByName('building-massing:4:13');
    expect(massing?.userData.buildingMassing).toEqual({
      buildingCount: 2,
      collisionPolicy: 'visual-only',
    });
    expect(group?.children.filter((child) => child.name.startsWith('building-massing:'))).toHaveLength(1);
    expect(physics.world.colliders.len()).toBe(0);

    // Buildings add no colliders: only Roadbed + schema-v1 support ground are active.
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
