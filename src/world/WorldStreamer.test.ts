import { describe, expect, it } from 'vitest';
import { WorldStreamer, type TileRuntimeAdapter } from './WorldStreamer';
import type { WorldSource } from './WorldSource';
import type { RuntimeOrigin, TileManifestEntry, TilePayload, WorldManifest, WorldPoint } from './types';

function tileEntry(ix: number): TileManifestEntry {
  return {
    tile_id: `${ix}:0`,
    index: [ix, 0],
    origin_m: [ix * 256, 0],
    file: `tiles/${ix}_0.json`,
    road_surface_count: 0,
    road_count: 0,
  };
}

function manifest(): WorldManifest {
  return {
    schema_version: 1,
    name: 'test-world',
    coordinate_system: {
      crs: 'EPSG:32118',
      units: 'metres',
      project_origin_wgs84: [-74.006, 40.7128],
      tile_size_m: 256,
    },
    bounds_wgs84: [-74, 40, -73, 41],
    tile_count: 3,
    tiles: [tileEntry(0), tileEntry(1), tileEntry(2)],
  };
}

function payload(entry: TileManifestEntry): TilePayload {
  return {
    schema_version: 1,
    tile_id: entry.tile_id,
    index: entry.index,
    origin_m: entry.origin_m,
    size_m: 256,
    road_surfaces: [],
    roads: [],
  };
}

class FakeSource implements WorldSource {
  constructor(private readonly worldManifest = manifest()) {}

  loadManifest(): Promise<WorldManifest> {
    return Promise.resolve(this.worldManifest);
  }

  loadTile(entry: TileManifestEntry): Promise<TilePayload> {
    return Promise.resolve(payload(entry));
  }
}

class FakeAdapter implements TileRuntimeAdapter {
  readonly attached = new Set<string>();
  readonly active = new Set<string>();
  rebases: WorldPoint[] = [];

  attachTile(tile: TilePayload, _runtimeOrigin: RuntimeOrigin): void {
    this.attached.add(tile.tile_id);
  }

  setPhysicsActive(tileId: string, active: boolean): number {
    if (active) this.active.add(tileId);
    else this.active.delete(tileId);
    return active ? 2 : 0;
  }

  detachTile(tileId: string): void {
    this.attached.delete(tileId);
    this.active.delete(tileId);
  }

  rebase(shift: WorldPoint): void {
    this.rebases.push(shift);
  }
}

describe('WorldStreamer', () => {
  it('bounds loaded state by the cache policy and releases tiles left behind', async () => {
    const adapter = new FakeAdapter();
    const streamer = new WorldStreamer(new FakeSource(), adapter, {
      physicsRadiusM: 0,
      renderRadiusM: 0,
      cacheRadiusM: 0,
    });
    await streamer.initialize();
    await streamer.update({ x: 100, y: 100 }, { x: 0, y: 0 });
    expect(streamer.debugSnapshot()).toMatchObject({
      loadedTiles: 1,
      activePhysicsTiles: 1,
      colliderCount: 2,
      unloadedTotal: 0,
    });
    expect(streamer.isPhysicsReadyAt({ x: 100, y: 100 })).toBe(true);

    await streamer.update({ x: 600, y: 100 }, { x: 512, y: 0 });
    expect(streamer.debugSnapshot()).toMatchObject({
      loadedTiles: 1,
      activePhysicsTiles: 1,
      colliderCount: 2,
      unloadedTotal: 1,
    });
    expect(adapter.attached.has('0:0')).toBe(false);
    expect(adapter.attached.has('2:0')).toBe(true);
  });

  it('does not report a player tile physics-ready until asynchronous loading and activation finish', async () => {
    const entry = tileEntry(0);
    let resolveTile: ((value: TilePayload) => void) | undefined;
    const source: WorldSource = {
      loadManifest: () => Promise.resolve({ ...manifest(), tile_count: 1, tiles: [entry] }),
      loadTile: () => new Promise<TilePayload>((resolve) => { resolveTile = resolve; }),
    };
    const adapter = new FakeAdapter();
    const streamer = new WorldStreamer(source, adapter, {
      physicsRadiusM: 0,
      renderRadiusM: 0,
      cacheRadiusM: 0,
    });
    await streamer.initialize();
    const update = streamer.update({ x: 100, y: 100 }, { x: 0, y: 0 });
    expect(streamer.debugSnapshot().loadingTiles).toBe(1);
    expect(streamer.isPhysicsReadyAt({ x: 100, y: 100 })).toBe(false);
    expect(resolveTile).toBeDefined();
    resolveTile?.(payload(entry));
    await update;
    expect(streamer.isPhysicsReadyAt({ x: 100, y: 100 })).toBe(true);
  });

  it('forwards floating-origin shifts without changing tile identities', async () => {
    const adapter = new FakeAdapter();
    const streamer = new WorldStreamer(new FakeSource(), adapter);
    await streamer.initialize();
    streamer.rebase({ x: 512, y: -256 });
    expect(adapter.rebases).toEqual([{ x: 512, y: -256 }]);
  });
});
