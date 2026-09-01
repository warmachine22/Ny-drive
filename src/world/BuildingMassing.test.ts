import { describe, expect, it } from 'vitest';
import { buildBuildingMassingGeometry } from './BuildingMassing';
import type { TileBuilding } from './types';

function building(id: string, x: number, heightM: number, baseElevationM = 0): TileBuilding {
  return {
    stable_id: `nyc-building-footprints:${id}`,
    source_id: id,
    source_key: 'nyc-building-footprints',
    feature_code: 2100,
    bin: null,
    name: null,
    construction_year: null,
    height_m: heightM,
    height_source: 'nyc-height-roof',
    base_elevation_m: baseElevationM,
    base_elevation_source: 'test',
    source_ground_elevation_m: null,
    polygons: [
      {
        outer: [
          [x, 10],
          [x + 8, 10],
          [x + 8, 18],
          [x, 18],
          [x, 10],
        ],
        holes: [],
      },
    ],
  };
}

describe('buildBuildingMassingGeometry', () => {
  it('merges multiple footprints into one bounded tile geometry', () => {
    const geometry = buildBuildingMassingGeometry([
      building('1', 10, 12, 3),
      building('2', 30, 6, 3),
    ]);

    expect(geometry).not.toBeNull();
    expect(geometry?.getAttribute('position').count).toBeGreaterThan(0);
    geometry?.computeBoundingBox();
    expect(geometry?.boundingBox?.min.y).toBeCloseTo(3, 5);
    expect(geometry?.boundingBox?.max.y).toBeCloseTo(15, 5);
    expect(geometry?.boundingBox?.max.x).toBeCloseTo(38, 5);
    geometry?.dispose();
  });
});
