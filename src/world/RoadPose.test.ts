import { describe, expect, it } from 'vitest';
import { findNearestRoadPose } from './RoadPose';
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
        stable_id: 'roadbed:test',
        source_id: 'rb',
        source_key: 'roadbed',
        feature_code: 3500,
        sub_code: null,
        status: 'active',
        polygons: [
          {
            outer: [[0, 0], [100, 0], [100, 30], [0, 30], [0, 0]],
            holes: [],
          },
        ],
      },
    ],
    roads: [
      {
        stable_id: 'centerline:test',
        source_id: 'cl',
        source_key: 'centerline',
        name: 'TEST AVE',
        directionality: 'forward',
        lanes: 2,
        lanes_forward: 2,
        lanes_backward: 0,
        width_m: 12,
        road_class: 'street',
        bridge: false,
        tunnel: false,
        layer: 0,
        from_level_code: null,
        to_level_code: null,
        paths: [[[0, 15], [100, 15]]],
      },
    ],
  };
}

describe('findNearestRoadPose', () => {
  it('projects onto centerline geometry and returns heading and elevation', () => {
    const pose = findNearestRoadPose([tile()], { x: 1074, y: 3360 });
    expect(pose).not.toBeNull();
    expect(pose?.source).toBe('centerline');
    expect(pose?.roadName).toBe('TEST AVE');
    expect(pose?.position.x).toBeCloseTo(1074);
    expect(pose?.position.y).toBeCloseTo(3343);
    expect(pose?.elevationM).toBe(0);
    expect(pose?.headingRad).toBeCloseTo(-Math.PI / 2);
    expect(pose?.distanceM).toBeCloseTo(17);
  });

  it('falls back to a Roadbed interior candidate when centerlines are unavailable', () => {
    const withoutCenterline = tile();
    withoutCenterline.roads = [];
    const pose = findNearestRoadPose([withoutCenterline], { x: 1024, y: 3328 });
    expect(pose?.source).toBe('roadbed');
    expect(pose?.position.x).toBeCloseTo(1074);
    expect(pose?.position.y).toBeCloseTo(3343);
    expect(pose?.elevationM).toBe(0);
  });

  it('uses elevation to disambiguate stacked roads at the same horizontal crossing', () => {
    const elevated = tile();
    elevated.schema_version = 2;
    elevated.roads = [
      {
        ...elevated.roads[0]!,
        stable_id: 'centerline:upper',
        source_id: 'upper',
        name: 'UPPER',
        paths: [[[0, 15, 12], [100, 15, 12]]],
      },
      {
        ...elevated.roads[0]!,
        stable_id: 'centerline:lower',
        source_id: 'lower',
        name: 'LOWER',
        paths: [[[50, -35, 2], [50, 65, 2]]],
      },
    ];
    const query = { x: 1074, y: 3343 };
    expect(findNearestRoadPose([elevated], query, 11.5)?.roadName).toBe('UPPER');
    expect(findNearestRoadPose([elevated], query, 2.5)?.roadName).toBe('LOWER');
  });
});
