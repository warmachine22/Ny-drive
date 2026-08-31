import RAPIER from '@dimforge/rapier3d-compat';
import type { PhysicsRuntime } from '../physics/PhysicsWorld';
import type { RuntimeOrigin, TilePayload, WorldPoint } from './types';

type RapierWorld = PhysicsRuntime['world'];
type RapierCollider = ReturnType<RapierWorld['createCollider']>;

export const SUPPORT_SURFACE_Y_M = -0.25;
const SUPPORT_THICKNESS_M = 0.2;

interface ActiveSupport {
  collider: RapierCollider;
}

/**
 * The current development fixture is flat, but T010 will introduce real elevation,
 * bridges and tunnels. Never manufacture a flat support slab for a tile that already
 * advertises explicit vertical-road semantics; that would turn an overpass/tunnel into
 * a false intersection. T010 can replace this conservative prototype policy with real
 * terrain/elevation geometry.
 */
export function isFlatSupportEligible(tile: TilePayload): boolean {
  return !tile.roads.some((road) => road.bridge || road.tunnel || road.layer !== 0);
}

export class SupportGroundManager {
  private readonly active = new Map<string, ActiveSupport>();

  constructor(private readonly world: RapierWorld) {}

  activateTile(tile: TilePayload, runtimeOrigin: RuntimeOrigin): number {
    if (this.active.has(tile.tile_id)) return 1;
    if (!isFlatSupportEligible(tile)) return 0;

    const halfSize = tile.size_m / 2;
    const halfThickness = SUPPORT_THICKNESS_M / 2;
    const collider = this.world.createCollider(
      RAPIER.ColliderDesc.cuboid(halfSize, halfThickness, halfSize)
        .setTranslation(
          tile.origin_m[0] - runtimeOrigin.x + halfSize,
          SUPPORT_SURFACE_Y_M - halfThickness,
          tile.origin_m[1] - runtimeOrigin.y + halfSize,
        )
        .setFriction(0.72)
        .setRestitution(0),
    );
    this.active.set(tile.tile_id, { collider });
    return 1;
  }

  deactivateTile(tileId: string): void {
    const support = this.active.get(tileId);
    if (!support) return;
    this.world.removeCollider(support.collider, false);
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

  dispose(): void {
    for (const tileId of [...this.active.keys()]) this.deactivateTile(tileId);
  }
}
