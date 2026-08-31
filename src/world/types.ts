export interface WorldPoint {
  x: number;
  y: number;
}

export interface RuntimeOrigin extends WorldPoint {}

export type TileLifecycle = 'loading' | 'ready' | 'active-physics' | 'cached' | 'unloaded';
export type TilePoint = [number, number] | [number, number, number];

export interface TileManifestEntry {
  tile_id: string;
  index: [number, number];
  origin_m: [number, number];
  file: string;
  road_surface_count: number;
  road_count: number;
}

export interface WorldManifest {
  schema_version: number;
  name: string;
  coordinate_system: {
    crs: string;
    units: string;
    project_origin_wgs84: [number, number];
    tile_size_m: number;
  };
  bounds_wgs84: [number, number, number, number];
  tile_count: number;
  tiles: TileManifestEntry[];
}

export interface TilePolygon {
  outer: TilePoint[];
  holes: TilePoint[][];
}

export interface TileRoadSurface {
  stable_id: string;
  source_id: string;
  source_key: string;
  feature_code: number | null;
  sub_code: number | null;
  status: string | null;
  polygons: TilePolygon[];
  vertical_status?: 'resolved' | 'unresolved' | 'terrain-only';
  associated_road_id?: string | null;
  elevation_source?: string;
}

export interface TileRoad {
  stable_id: string;
  source_id: string;
  source_key: string;
  name: string | null;
  directionality: 'both' | 'forward' | 'reverse';
  lanes: number | null;
  lanes_forward: number | null;
  lanes_backward: number | null;
  width_m: number | null;
  road_class: string | null;
  bridge: boolean;
  tunnel: boolean;
  layer: number;
  from_level_code: string | number | null;
  to_level_code: string | number | null;
  paths: TilePoint[][];
  ramp?: boolean;
  vertical_structure?: 'at-grade' | 'bridge' | 'tunnel' | 'ramp';
  vertical_level_source?: string;
  from_level?: number;
  to_level?: number;
  elevation_source?: string;
}

export interface VerticalDiagnostic {
  severity: 'warning' | 'error';
  code: string;
  feature_id: string;
  message: string;
}

export interface TilePayload {
  schema_version: number;
  tile_id: string;
  index: [number, number];
  origin_m: [number, number];
  size_m: number;
  road_surfaces: TileRoadSurface[];
  roads: TileRoad[];
  vertical_diagnostics?: VerticalDiagnostic[];
}

export interface StreamDebugSnapshot {
  loadedTiles: number;
  loadingTiles: number;
  readyTiles: number;
  activePhysicsTiles: number;
  cachedTiles: number;
  renderedTiles: number;
  colliderCount: number;
  unloadedTotal: number;
}

export function tilePointElevationM(point: TilePoint): number {
  return point[2] ?? 0;
}
