import type { WorldSource } from './WorldSource';
import type {
  RuntimeOrigin,
  StreamDebugSnapshot,
  TileLifecycle,
  TileManifestEntry,
  TilePayload,
  WorldManifest,
  WorldPoint,
} from './types';

export interface StreamConfig {
  physicsRadiusM: number;
  renderRadiusM: number;
  cacheRadiusM: number;
}

export interface TileRuntimeAdapter {
  attachTile(tile: TilePayload, runtimeOrigin: RuntimeOrigin): Promise<void> | void;
  setPhysicsActive(tileId: string, active: boolean): Promise<number> | number;
  detachTile(tileId: string): Promise<void> | void;
  rebase(shift: WorldPoint): void;
}

interface TileRecord {
  entry: TileManifestEntry;
  state: TileLifecycle;
  data: TilePayload | undefined;
  colliderCount: number;
}

const DEFAULT_CONFIG: StreamConfig = {
  physicsRadiusM: 300,
  renderRadiusM: 460,
  cacheRadiusM: 720,
};

function distanceToTile(point: WorldPoint, entry: TileManifestEntry, tileSizeM: number): number {
  const [originX, originY] = entry.origin_m;
  const maxX = originX + tileSizeM;
  const maxY = originY + tileSizeM;
  const dx = point.x < originX ? originX - point.x : point.x > maxX ? point.x - maxX : 0;
  const dy = point.y < originY ? originY - point.y : point.y > maxY ? point.y - maxY : 0;
  return Math.hypot(dx, dy);
}

export function selectTiles(
  manifest: WorldManifest,
  point: WorldPoint,
  radiusM: number,
): Set<string> {
  return new Set(
    manifest.tiles
      .filter((entry) => distanceToTile(point, entry, manifest.coordinate_system.tile_size_m) <= radiusM)
      .map((entry) => entry.tile_id),
  );
}

export class WorldStreamer {
  private manifest: WorldManifest | undefined;
  private readonly entries = new Map<string, TileManifestEntry>();
  private readonly records = new Map<string, TileRecord>();
  private unloadedTotal = 0;

  constructor(
    private readonly source: WorldSource,
    private readonly adapter: TileRuntimeAdapter,
    private readonly config: StreamConfig = DEFAULT_CONFIG,
  ) {
    if (config.physicsRadiusM > config.renderRadiusM || config.renderRadiusM > config.cacheRadiusM) {
      throw new Error('Streaming radii must satisfy physics <= render <= cache.');
    }
  }

  async initialize(): Promise<WorldManifest> {
    const manifest = await this.source.loadManifest();
    if (manifest.schema_version !== 1 || manifest.coordinate_system.units !== 'metres') {
      throw new Error('Unsupported world manifest coordinate contract.');
    }
    this.manifest = manifest;
    this.entries.clear();
    for (const entry of manifest.tiles) {
      this.entries.set(entry.tile_id, entry);
    }
    return manifest;
  }

  worldCenter(): WorldPoint {
    const manifest = this.requireManifest();
    if (manifest.tiles.length === 0) return { x: 0, y: 0 };
    const tileSize = manifest.coordinate_system.tile_size_m;
    const minX = Math.min(...manifest.tiles.map((entry) => entry.origin_m[0]));
    const minY = Math.min(...manifest.tiles.map((entry) => entry.origin_m[1]));
    const maxX = Math.max(...manifest.tiles.map((entry) => entry.origin_m[0] + tileSize));
    const maxY = Math.max(...manifest.tiles.map((entry) => entry.origin_m[1] + tileSize));
    return { x: (minX + maxX) / 2, y: (minY + maxY) / 2 };
  }

  async update(playerGlobal: WorldPoint, runtimeOrigin: RuntimeOrigin): Promise<void> {
    const manifest = this.requireManifest();
    const physics = selectTiles(manifest, playerGlobal, this.config.physicsRadiusM);
    const render = selectTiles(manifest, playerGlobal, this.config.renderRadiusM);
    const cache = selectTiles(manifest, playerGlobal, this.config.cacheRadiusM);

    await Promise.all([...cache].map((id) => this.ensureLoaded(id)));

    for (const id of cache) {
      const record = this.records.get(id);
      if (!record?.data) continue;
      if (!render.has(id)) {
        await this.cacheRecord(record);
        continue;
      }
      if (record.state === 'cached') {
        await this.adapter.attachTile(record.data, runtimeOrigin);
        record.state = 'ready';
      }
      if (physics.has(id) && record.state === 'ready') {
        record.colliderCount = await this.adapter.setPhysicsActive(id, true);
        record.state = 'active-physics';
      } else if (!physics.has(id) && record.state === 'active-physics') {
        await this.adapter.setPhysicsActive(id, false);
        record.colliderCount = 0;
        record.state = 'ready';
      }
    }

    for (const [id, record] of [...this.records]) {
      if (!cache.has(id)) {
        await this.releaseRecord(id, record);
      }
    }
  }

  isPhysicsReadyAt(point: WorldPoint): boolean {
    const manifest = this.requireManifest();
    const tileSize = manifest.coordinate_system.tile_size_m;
    const ix = Math.floor(point.x / tileSize);
    const iy = Math.floor(point.y / tileSize);
    const record = this.records.get(`${ix}:${iy}`);
    return record?.state === 'active-physics';
  }

  rebase(shift: WorldPoint): void {
    if (shift.x === 0 && shift.y === 0) return;
    this.adapter.rebase(shift);
  }

  debugSnapshot(): StreamDebugSnapshot {
    let loadingTiles = 0;
    let readyTiles = 0;
    let activePhysicsTiles = 0;
    let cachedTiles = 0;
    let colliderCount = 0;
    for (const record of this.records.values()) {
      if (record.state === 'loading') loadingTiles += 1;
      if (record.state === 'ready') readyTiles += 1;
      if (record.state === 'active-physics') activePhysicsTiles += 1;
      if (record.state === 'cached') cachedTiles += 1;
      colliderCount += record.colliderCount;
    }
    return {
      loadedTiles: this.records.size,
      loadingTiles,
      readyTiles,
      activePhysicsTiles,
      cachedTiles,
      renderedTiles: readyTiles + activePhysicsTiles,
      colliderCount,
      unloadedTotal: this.unloadedTotal,
    };
  }

  async dispose(): Promise<void> {
    for (const [id, record] of [...this.records]) {
      await this.releaseRecord(id, record);
    }
  }

  private requireManifest(): WorldManifest {
    if (!this.manifest) throw new Error('WorldStreamer.initialize() must complete before use.');
    return this.manifest;
  }

  private async ensureLoaded(id: string): Promise<void> {
    if (this.records.has(id)) return;
    const entry = this.entries.get(id);
    if (!entry) return;
    const record: TileRecord = { entry, state: 'loading', data: undefined, colliderCount: 0 };
    this.records.set(id, record);
    try {
      record.data = await this.source.loadTile(entry);
      record.state = 'cached';
    } catch (error) {
      this.records.delete(id);
      throw error;
    }
  }

  private async cacheRecord(record: TileRecord): Promise<void> {
    if (record.state === 'active-physics') {
      await this.adapter.setPhysicsActive(record.entry.tile_id, false);
      record.colliderCount = 0;
      record.state = 'ready';
    }
    if (record.state === 'ready') {
      await this.adapter.detachTile(record.entry.tile_id);
      record.state = 'cached';
    }
  }

  private async releaseRecord(id: string, record: TileRecord): Promise<void> {
    await this.cacheRecord(record);
    record.state = 'unloaded';
    record.data = undefined;
    this.records.delete(id);
    this.unloadedTotal += 1;
  }
}
