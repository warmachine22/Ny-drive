import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import type { TileBuilding, TilePoint, TilePolygon } from './types';

function appendRing(path: THREE.Path | THREE.Shape, points: TilePoint[]): boolean {
  if (points.length < 3) return false;
  const first = points[0];
  if (!first) return false;
  path.moveTo(first[0], -first[1]);
  for (const point of points.slice(1)) path.lineTo(point[0], -point[1]);
  path.closePath();
  return true;
}

function buildingPolygonGeometry(building: TileBuilding, polygon: TilePolygon): THREE.BufferGeometry | null {
  const shape = new THREE.Shape();
  if (!appendRing(shape, polygon.outer)) return null;
  for (const holePoints of polygon.holes) {
    const hole = new THREE.Path();
    if (appendRing(hole, holePoints)) shape.holes.push(hole);
  }

  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: Math.max(0.1, building.height_m),
    bevelEnabled: false,
    steps: 1,
    curveSegments: 1,
  });
  // Shape XY -> world XZ, extrusion +Z -> world +Y.
  geometry.rotateX(-Math.PI / 2);
  geometry.translate(0, building.base_elevation_m, 0);
  geometry.deleteAttribute('uv');
  return geometry;
}

export function buildBuildingMassingGeometry(buildings: readonly TileBuilding[]): THREE.BufferGeometry | null {
  const parts: THREE.BufferGeometry[] = [];
  try {
    for (const building of buildings) {
      if (!(building.height_m > 0)) continue;
      for (const polygon of building.polygons) {
        const geometry = buildingPolygonGeometry(building, polygon);
        if (geometry) parts.push(geometry);
      }
    }
    if (parts.length === 0) return null;
    const merged = mergeGeometries(parts, false);
    if (!merged) throw new Error('Failed to merge building massing geometry.');
    merged.computeBoundingBox();
    merged.computeBoundingSphere();
    return merged;
  } finally {
    for (const part of parts) part.dispose();
  }
}
