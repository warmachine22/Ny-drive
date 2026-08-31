import type { TilePayload, WorldPoint } from './types';

export interface RoadPose {
  position: WorldPoint;
  headingRad: number;
  source: 'centerline' | 'roadbed';
  roadName: string | null;
  distanceM: number;
}

interface SegmentCandidate {
  position: WorldPoint;
  headingRad: number;
  roadName: string | null;
  distanceM: number;
}

function distance(a: WorldPoint, b: WorldPoint): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function segmentPose(
  query: WorldPoint,
  a: WorldPoint,
  b: WorldPoint,
  roadName: string | null,
  reverse: boolean,
): SegmentCandidate | null {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared < 0.000001) return null;
  const t = Math.min(
    1,
    Math.max(0, ((query.x - a.x) * dx + (query.y - a.y) * dy) / lengthSquared),
  );
  const position = { x: a.x + dx * t, y: a.y + dy * t };
  const headingDx = reverse ? -dx : dx;
  const headingDy = reverse ? -dy : dy;
  // Vehicle local forward is -Z. WorldPoint.y maps to Three/Rapier Z.
  const headingRad = Math.atan2(-headingDx, -headingDy);
  return { position, headingRad, roadName, distanceM: distance(query, position) };
}

function roadbedFallback(tile: TilePayload, query: WorldPoint): RoadPose | null {
  let best: RoadPose | null = null;
  for (const surface of tile.road_surfaces) {
    for (const polygon of surface.polygons) {
      const ring = polygon.outer;
      if (ring.length < 3) continue;
      const isClosed =
        ring.length > 1 &&
        ring[0]?.[0] === ring[ring.length - 1]?.[0] &&
        ring[0]?.[1] === ring[ring.length - 1]?.[1];
      const count = isClosed ? ring.length - 1 : ring.length;
      if (count < 3) continue;
      let x = 0;
      let y = 0;
      for (let index = 0; index < count; index += 1) {
        const point = ring[index];
        if (!point) continue;
        x += point[0];
        y += point[1];
      }
      const position = {
        x: tile.origin_m[0] + x / count,
        y: tile.origin_m[1] + y / count,
      };
      const candidate: RoadPose = {
        position,
        headingRad: 0,
        source: 'roadbed',
        roadName: null,
        distanceM: distance(query, position),
      };
      if (!best || candidate.distanceM < best.distanceM) best = candidate;
    }
  }
  return best;
}

export function findNearestRoadPose(tiles: readonly TilePayload[], query: WorldPoint): RoadPose | null {
  let bestCenterline: RoadPose | null = null;

  for (const tile of tiles) {
    for (const road of tile.roads) {
      for (const path of road.paths) {
        for (let index = 0; index + 1 < path.length; index += 1) {
          const a = path[index];
          const b = path[index + 1];
          if (!a || !b) continue;
          const candidate = segmentPose(
            query,
            { x: tile.origin_m[0] + a[0], y: tile.origin_m[1] + a[1] },
            { x: tile.origin_m[0] + b[0], y: tile.origin_m[1] + b[1] },
            road.name,
            road.directionality === 'reverse',
          );
          if (!candidate) continue;
          const pose: RoadPose = { ...candidate, source: 'centerline' };
          if (!bestCenterline || pose.distanceM < bestCenterline.distanceM) {
            bestCenterline = pose;
          }
        }
      }
    }
  }

  if (bestCenterline) return bestCenterline;

  let bestRoadbed: RoadPose | null = null;
  for (const tile of tiles) {
    const candidate = roadbedFallback(tile, query);
    if (candidate && (!bestRoadbed || candidate.distanceM < bestRoadbed.distanceM)) {
      bestRoadbed = candidate;
    }
  }
  return bestRoadbed;
}
