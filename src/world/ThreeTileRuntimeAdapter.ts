import * as THREE from 'three';
import type { PhysicsRuntime } from '../physics/PhysicsWorld';
import { RoadCollisionManager } from './RoadCollision';
import {
  isFlatSupportEligible,
  SUPPORT_SURFACE_Y_M,
  SupportGroundManager,
} from './SupportGround';
import type { TileRuntimeAdapter } from './WorldStreamer';
import type { RuntimeOrigin, TilePayload, WorldPoint } from './types';

interface TileVisual {
  tile: TilePayload;
  group: THREE.Group;
  geometries: THREE.BufferGeometry[];
  physicsActive: boolean;
}

const ROAD_VISUAL_Y_M = 0.025;

export class ThreeTileRuntimeAdapter implements TileRuntimeAdapter {
  private readonly visuals = new Map<string, TileVisual>();
  private readonly collisions: RoadCollisionManager;
  private readonly support: SupportGroundManager;
  private runtimeOrigin: RuntimeOrigin = { x: 0, y: 0 };
  private readonly roadMaterial = new THREE.MeshStandardMaterial({
    color: 0x313a42,
    roughness: 0.92,
    metalness: 0.02,
    side: THREE.DoubleSide,
  });
  private readonly supportMaterial = new THREE.MeshStandardMaterial({
    color: 0x202832,
    roughness: 1,
    metalness: 0,
    side: THREE.DoubleSide,
  });
  private readonly centerlineMaterial = new THREE.LineBasicMaterial({ color: 0xa7b1bb });

  constructor(
    private readonly scene: THREE.Scene,
    physics: PhysicsRuntime,
  ) {
    this.collisions = new RoadCollisionManager(physics.world);
    this.support = new SupportGroundManager(physics.world);
  }

  attachTile(tile: TilePayload, runtimeOrigin: RuntimeOrigin): void {
    if (this.visuals.has(tile.tile_id)) return;
    this.runtimeOrigin = { ...runtimeOrigin };
    const group = new THREE.Group();
    group.name = `world-tile:${tile.tile_id}`;
    group.position.set(
      tile.origin_m[0] - runtimeOrigin.x,
      ROAD_VISUAL_Y_M,
      tile.origin_m[1] - runtimeOrigin.y,
    );
    const geometries: THREE.BufferGeometry[] = [];

    if (isFlatSupportEligible(tile)) {
      const supportGeometry = new THREE.PlaneGeometry(tile.size_m, tile.size_m);
      geometries.push(supportGeometry);
      const supportMesh = new THREE.Mesh(supportGeometry, this.supportMaterial);
      supportMesh.name = `support-ground:${tile.tile_id}`;
      supportMesh.rotation.x = -Math.PI / 2;
      supportMesh.position.set(
        tile.size_m / 2,
        SUPPORT_SURFACE_Y_M - ROAD_VISUAL_Y_M,
        tile.size_m / 2,
      );
      supportMesh.userData.supportGround = true;
      group.add(supportMesh);
    }

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
        mesh.userData.roadSurface = {
          stableId: surface.stable_id,
          sourceId: surface.source_id,
          sourceKey: surface.source_key,
          featureCode: surface.feature_code,
          subCode: surface.sub_code,
          status: surface.status,
        };
        group.add(mesh);
      }
    }

    for (const road of tile.roads) {
      for (const path of road.paths) {
        if (path.length < 2) continue;
        const geometry = new THREE.BufferGeometry().setFromPoints(
          path.map(([x, y]) => new THREE.Vector3(x, 0.01, y)),
        );
        geometries.push(geometry);
        const line = new THREE.Line(geometry, this.centerlineMaterial);
        line.userData.road = {
          stableId: road.stable_id,
          sourceId: road.source_id,
          sourceKey: road.source_key,
          name: road.name,
          directionality: road.directionality,
          lanes: road.lanes,
          lanesForward: road.lanes_forward,
          lanesBackward: road.lanes_backward,
          widthM: road.width_m,
          roadClass: road.road_class,
          layer: road.layer,
          fromLevelCode: road.from_level_code,
          toLevelCode: road.to_level_code,
        };
        group.add(line);
      }
    }

    this.scene.add(group);
    this.visuals.set(tile.tile_id, { tile, group, geometries, physicsActive: false });
  }

  setPhysicsActive(tileId: string, active: boolean): number {
    const visual = this.visuals.get(tileId);
    if (!visual && active) {
      throw new Error(`Cannot activate physics before tile render initialization: ${tileId}`);
    }
    if (!visual) return 0;

    if (active) {
      const roadColliderCount = this.collisions.activateTile(visual.tile, this.runtimeOrigin);
      const supportColliderCount = this.support.activateTile(visual.tile, this.runtimeOrigin);
      const colliderCount = roadColliderCount + supportColliderCount;
      visual.physicsActive = colliderCount > 0;
      return colliderCount;
    }

    this.collisions.deactivateTile(tileId);
    this.support.deactivateTile(tileId);
    visual.physicsActive = false;
    return 0;
  }

  detachTile(tileId: string): void {
    const visual = this.visuals.get(tileId);
    if (!visual) return;
    this.collisions.deactivateTile(tileId);
    this.support.deactivateTile(tileId);
    this.scene.remove(visual.group);
    for (const geometry of visual.geometries) geometry.dispose();
    this.visuals.delete(tileId);
  }

  rebase(shift: WorldPoint): void {
    if (shift.x === 0 && shift.y === 0) return;
    this.runtimeOrigin = {
      x: this.runtimeOrigin.x + shift.x,
      y: this.runtimeOrigin.y + shift.y,
    };
    for (const visual of this.visuals.values()) {
      visual.group.position.x -= shift.x;
      visual.group.position.z -= shift.y;
    }
    this.collisions.rebase(shift);
    this.support.rebase(shift);
  }

  dispose(): void {
    this.collisions.dispose();
    this.support.dispose();
    for (const tileId of [...this.visuals.keys()]) this.detachTile(tileId);
    this.roadMaterial.dispose();
    this.supportMaterial.dispose();
    this.centerlineMaterial.dispose();
  }
}
