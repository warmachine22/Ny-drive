import * as THREE from 'three';
import type { PhysicsRuntime } from '../physics/PhysicsWorld';
import { buildRoadSurfaceCollisionMesh, RoadCollisionManager } from './RoadCollision';
import {
  isFlatSupportEligible,
  SUPPORT_SURFACE_Y_M,
  SupportGroundManager,
} from './SupportGround';
import type { TileRuntimeAdapter } from './WorldStreamer';
import {
  tilePointElevationM,
  type RuntimeOrigin,
  type TilePayload,
  type WorldPoint,
} from './types';

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
      0,
      tile.origin_m[1] - runtimeOrigin.y,
    );
    const geometries: THREE.BufferGeometry[] = [];

    if (isFlatSupportEligible(tile)) {
      const supportGeometry = new THREE.PlaneGeometry(tile.size_m, tile.size_m);
      geometries.push(supportGeometry);
      const supportMesh = new THREE.Mesh(supportGeometry, this.supportMaterial);
      supportMesh.name = `support-ground:${tile.tile_id}`;
      supportMesh.rotation.x = -Math.PI / 2;
      supportMesh.position.set(tile.size_m / 2, SUPPORT_SURFACE_Y_M, tile.size_m / 2);
      supportMesh.userData.supportGround = true;
      group.add(supportMesh);
    }

    for (const surface of tile.road_surfaces) {
      const meshData = buildRoadSurfaceCollisionMesh(surface);
      if (meshData.triangleCount === 0) continue;
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(meshData.vertices, 3));
      geometry.setIndex(new THREE.BufferAttribute(meshData.indices, 1));
      geometry.computeVertexNormals();
      geometries.push(geometry);
      const mesh = new THREE.Mesh(geometry, this.roadMaterial);
      mesh.position.y = ROAD_VISUAL_Y_M;
      mesh.userData.roadSurface = {
        stableId: surface.stable_id,
        sourceId: surface.source_id,
        sourceKey: surface.source_key,
        featureCode: surface.feature_code,
        subCode: surface.sub_code,
        status: surface.status,
        verticalStatus: surface.vertical_status ?? 'flat-schema-v1',
        associatedRoadId: surface.associated_road_id ?? null,
      };
      group.add(mesh);
    }

    for (const road of tile.roads) {
      for (const path of road.paths) {
        if (path.length < 2) continue;
        const geometry = new THREE.BufferGeometry().setFromPoints(
          path.map(
            (point) =>
              new THREE.Vector3(
                point[0],
                tilePointElevationM(point) + ROAD_VISUAL_Y_M + 0.01,
                point[1],
              ),
          ),
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
          ramp: road.ramp ?? false,
          verticalStructure: road.vertical_structure ?? 'flat-schema-v1',
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
