import { describe, expect, it } from 'vitest';
import { createPhysicsRuntime } from '../physics/PhysicsWorld';
import { isFlatSupportEligible, SupportGroundManager } from './SupportGround';
import type { TilePayload } from './types';

function fixture(overrides: Partial<TilePayload['roads'][number]> = {}): TilePayload {
  return {
    schema_version: 1,
    tile_id: '4:13',
    index: [4, 13],
    origin_m: [1024, 3328],
    size_m: 256,
    road_surfaces: [],
    roads: [{
      stable_id: 'road:1',
      source_id: '1',
      source_key: 'fixture',
      name: 'TEST ST',
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
      paths: [[[0, 0], [100, 0]]],
      ...overrides,
    }],
  };
}

describe('SupportGroundManager', () => {
  it('supports flat prototype tiles and bounds collider lifetime to activation', async () => {
    const physics = await createPhysicsRuntime();
    const support = new SupportGroundManager(physics.world);
    const tile = fixture();

    expect(isFlatSupportEligible(tile)).toBe(true);
    expect(support.activateTile(tile, { x: 1024, y: 3328 })).toBe(1);
    expect(support.colliderCount()).toBe(1);
    expect(physics.world.colliders.len()).toBe(1);
    expect(support.activateTile(tile, { x: 1024, y: 3328 })).toBe(1);
    expect(physics.world.colliders.len()).toBe(1);

    support.rebase({ x: 256, y: -128 });
    expect(support.colliderCount()).toBe(1);

    support.deactivateTile(tile.tile_id);
    expect(support.colliderCount()).toBe(0);
    expect(physics.world.colliders.len()).toBe(0);
    support.dispose();
    physics.dispose();
  });

  it('refuses to flatten tiles carrying bridge tunnel or nonzero layer semantics', () => {
    expect(isFlatSupportEligible(fixture({ bridge: true }))).toBe(false);
    expect(isFlatSupportEligible(fixture({ tunnel: true }))).toBe(false);
    expect(isFlatSupportEligible(fixture({ layer: 1 }))).toBe(false);
    expect(isFlatSupportEligible(fixture({ layer: -1 }))).toBe(false);
  });
});
