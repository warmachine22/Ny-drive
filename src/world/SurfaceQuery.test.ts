import { describe, expect, it } from 'vitest';
import { surfaceKindAtTile } from './SurfaceQuery';
import type { TilePayload } from './types';

function tile(): TilePayload {
  return {
    schema_version: 1,
    tile_id: '0:0',
    index: [0, 0],
    origin_m: [0, 0],
    size_m: 100,
    road_surfaces: [{
      stable_id: 'surface:1',
      source_id: '1',
      source_key: 'fixture',
      feature_code: null,
      sub_code: null,
      status: null,
      polygons: [{ outer: [[10, 10], [30, 10], [30, 30], [10, 30], [10, 10]], holes: [] }],
    }],
    roads: [{
      stable_id: 'road:1',
      source_id: '1',
      source_key: 'fixture',
      name: 'TEST ST',
      directionality: 'both',
      lanes: 2,
      lanes_forward: null,
      lanes_backward: null,
      width_m: 10,
      road_class: 'General_use',
      bridge: false,
      tunnel: false,
      layer: 0,
      from_level_code: null,
      to_level_code: null,
      paths: [[[10, 20], [30, 20]]],
    }],
  };
}

describe('surfaceKindAtTile', () => {
  it('prefers Roadbed inside the authoritative polygon and support elsewhere in an eligible tile', () => {
    const fixture = tile();
    expect(surfaceKindAtTile(fixture, { x: 20, y: 20 })).toBe('roadbed');
    expect(surfaceKindAtTile(fixture, { x: 60, y: 60 })).toBe('support');
    expect(surfaceKindAtTile(fixture, { x: 120, y: 60 })).toBe('none');
  });

  it('does not report support for a vertically structured tile', () => {
    const fixture = tile();
    fixture.roads[0]!.bridge = true;
    expect(surfaceKindAtTile(fixture, { x: 60, y: 60 })).toBe('none');
  });
});
