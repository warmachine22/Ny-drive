import type { TilePayload, TilePolygon, WorldPoint } from './types';

export type WorldSurfaceKind = 'roadbed' | 'support' | 'none';

function pointInRing(point: [number, number], ring: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const a = ring[i];
    const b = ring[j];
    if (!a || !b) continue;
    const intersects =
      (a[1] > point[1]) !== (b[1] > point[1]) &&
      point[0] < ((b[0] - a[0]) * (point[1] - a[1])) / (b[1] - a[1]) + a[0];
    if (intersects) inside = !inside;
  }
  return inside;
}

function pointInPolygon(point: [number, number], polygon: TilePolygon): boolean {
  if (!pointInRing(point, polygon.outer)) return false;
  return !polygon.holes.some((hole) => pointInRing(point, hole));
}

export function isFlatSupportEligible(tile: TilePayload): boolean {
  return !tile.roads.some((road) => road.bridge || road.tunnel || road.layer !== 0);
}

export function surfaceKindAtTile(tile: TilePayload, point: WorldPoint): WorldSurfaceKind {
  const local: [number, number] = [
    point.x - tile.origin_m[0],
    point.y - tile.origin_m[1],
  ];
  if (
    local[0] < 0 ||
    local[1] < 0 ||
    local[0] > tile.size_m ||
    local[1] > tile.size_m
  ) {
    return 'none';
  }

  for (const surface of tile.road_surfaces) {
    for (const polygon of surface.polygons) {
      if (pointInPolygon(local, polygon)) return 'roadbed';
    }
  }
  return isFlatSupportEligible(tile) ? 'support' : 'none';
}
