import RAPIER from '@dimforge/rapier3d-compat';
import * as THREE from 'three';
import type { PhysicsRuntime } from '../physics/PhysicsWorld';
import type { RuntimeOrigin, TilePayload, TilePolygon, WorldPoint } from './types';

type RapierWorld = PhysicsRuntime['world'];
type RapierCollider = ReturnType<RapierWorld['createCollider']>;

export interface RoadCollisionMesh {
  vertices: Float32Array;
  indices: Uint32Array;
  triangleCount: number;
}

interface ActiveTileCollider {
  collider: RapierCollider;
  triangleCount: number;
}

function ringVectors(ring: [number, number][]): THREE.Vector2[] {
  const points = ring.map(([x, y]) => new THREE.Vector2(x, y));
  if (points.length > 1 && points[0]?.equals(points[points.length - 1] as THREE.Vector2)) {
    points.pop();
  }
  return points;
}

function triangulatePolygon(polygon: TilePolygon): THREE.Vector2[][] {
  const contour = ringVectors(polygon.outer);
  if (contour.length < 3) return [];
  const holes = polygon.holes.map(ringVectors).filter((ring) => ring.length >= 3);
  const points = [...contour, ...holes.flat()];
  const faces = THREE.ShapeUtils.triangulateShape(contour, holes);
  return faces.map((face) => {
    const a = face[0];
    const b = face[1];
    const c = face[2];
    if (a === undefined || b === undefined || c === undefined) {
      throw new Error('Three.js returned an incomplete road triangulation face.');
    }
    const first = points[a];
    const second = points[b];
    const third = points[c];
    if (!first || !second || !third) {
      throw new Error('Three.js returned an out-of-range road triangulation index.');
    }
    return [first, second, third];
  });
}

export function buildRoadCollisionMesh(tile: TilePayload): RoadCollisionMesh {
  const vertices: number[] = [];
  const indices: number[] = [];
  let vertexIndex = 0;

  for (const surface of tile.road_surfaces) {
    for (const polygon of surface.polygons) {
      for (const triangle of triangulatePolygon(polygon)) {
        for (const point of triangle) {
          vertices.push(point.x, 0, point.y);
          indices.push(vertexIndex);
          vertexIndex += 1;
        }
      }
    }
  }

  return {
    vertices: new Float32Array(vertices),
    indices: new Uint32Array(indices),
    triangleCount: indices.length / 3,
  };
}

export class RoadCollisionManager {
  private readonly active = new Map<string, ActiveTileCollider>();

  constructor(private readonly world: RapierWorld) {}

  activateTile(tile: TilePayload, runtimeOrigin: RuntimeOrigin): number {
    const existing = this.active.get(tile.tile_id);
    if (existing) return 1;

    const mesh = buildRoadCollisionMesh(tile);
    if (mesh.triangleCount === 0) return 0;

    const descriptor = RAPIER.ColliderDesc.trimesh(
      mesh.vertices,
      mesh.indices,
      RAPIER.TriMeshFlags.FIX_INTERNAL_EDGES,
    )
      .setTranslation(
        tile.origin_m[0] - runtimeOrigin.x,
        0,
        tile.origin_m[1] - runtimeOrigin.y,
      )
      .setFriction(1.05)
      .setRestitution(0);

    const collider = this.world.createCollider(descriptor);
    this.active.set(tile.tile_id, { collider, triangleCount: mesh.triangleCount });
    return 1;
  }

  deactivateTile(tileId: string): void {
    const active = this.active.get(tileId);
    if (!active) return;
    this.world.removeCollider(active.collider, false);
    this.active.delete(tileId);
  }

  rebase(shift: WorldPoint): void {
    if (shift.x === 0 && shift.y === 0) return;
    for (const { collider } of this.active.values()) {
      const translation = collider.translation();
      collider.setTranslation({
        x: translation.x - shift.x,
        y: translation.y,
        z: translation.z - shift.y,
      });
    }
  }

  colliderCount(): number {
    return this.active.size;
  }

  triangleCount(tileId: string): number {
    return this.active.get(tileId)?.triangleCount ?? 0;
  }

  dispose(): void {
    for (const tileId of [...this.active.keys()]) this.deactivateTile(tileId);
  }
}
