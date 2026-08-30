import * as THREE from 'three';
import type { TileRuntimeAdapter } from './WorldStreamer';
import type { RuntimeOrigin, TilePayload, WorldPoint } from './types';

interface TileVisual {
  group: THREE.Group;
  geometries: THREE.BufferGeometry[];
  physicsActive: boolean;
}

export class ThreeTileRuntimeAdapter implements TileRuntimeAdapter {
  private readonly visuals = new Map<string, TileVisual>();
  private readonly roadMaterial = new THREE.MeshStandardMaterial({
    color: 0x313a42,
    roughness: 0.92,
    metalness: 0.02,
    side: THREE.DoubleSide,
  });
  private readonly centerlineMaterial = new THREE.LineBasicMaterial({ color: 0xa7b1bb });

  constructor(private readonly scene: THREE.Scene) {}

  attachTile(tile: TilePayload, runtimeOrigin: RuntimeOrigin): void {
    if (this.visuals.has(tile.tile_id)) return;
    const group = new THREE.Group();
    group.name = `world-tile:${tile.tile_id}`;
    group.position.set(tile.origin_m[0] - runtimeOrigin.x, 0.025, tile.origin_m[1] - runtimeOrigin.y);
    const geometries: THREE.BufferGeometry[] = [];

    for (const surface of tile.road_surfaces) {
      for (const polygon of surface.polygons) {
        if (polygon.outer.length < 3) continue;
        const shape = new THREE.Shape(polygon.outer.map(([x, y]) => new THREE.Vector2(x, y)));
        shape.holes = polygon.holes.map(
          (hole) => new THREE.Path(hole.map(([x, y]) => new THREE.Vector2(x, y))),
        );
        const geometry = new THREE.ShapeGeometry(shape);
        geometries.push(geometry);
        const mesh = new THREE.Mesh(geometry, this.roadMaterial);
        mesh.rotation.x = Math.PI / 2;
        mesh.userData.stableId = surface.stable_id;
        group.add(mesh);
      }
    }

    for (const road of tile.roads) {
      for (const path of road.paths) {
        if (path.length < 2) continue;
        const geometry = new THREE.BufferGeometry().setFromPoints(
          path.map(([x, y]) => new THREE.Vector3(x, 0.035, y)),
        );
        geometries.push(geometry);
        const line = new THREE.Line(geometry, this.centerlineMaterial);
        line.userData.stableId = road.stable_id;
        group.add(line);
      }
    }

    this.scene.add(group);
    this.visuals.set(tile.tile_id, { group, geometries, physicsActive: false });
  }

  setPhysicsActive(tileId: string, active: boolean): number {
    const visual = this.visuals.get(tileId);
    if (!visual && active) {
      throw new Error(`Cannot activate physics before tile render initialization: ${tileId}`);
    }
    if (visual) visual.physicsActive = active;
    // T006 replaces this zero-count activation hook with real Rapier road colliders.
    return 0;
  }

  detachTile(tileId: string): void {
    const visual = this.visuals.get(tileId);
    if (!visual) return;
    this.scene.remove(visual.group);
    for (const geometry of visual.geometries) geometry.dispose();
    this.visuals.delete(tileId);
  }

  rebase(shift: WorldPoint): void {
    for (const visual of this.visuals.values()) {
      visual.group.position.x -= shift.x;
      visual.group.position.z -= shift.y;
    }
  }

  dispose(): void {
    for (const tileId of [...this.visuals.keys()]) this.detachTile(tileId);
    this.roadMaterial.dispose();
    this.centerlineMaterial.dispose();
  }
}
