# Citywide five-borough build

T012 extends the same offline compiler used by the Flatiron development slice to the complete New York City road world. The browser still consumes only compiled 256 m tiles; raw NYC GIS and DEM files remain compiler inputs and are not parsed at runtime.

## Why citywide acquisition is paginated

The official NYC Open Data endpoints are city-scale datasets (roughly one hundred thousand Roadbed features and more than one hundred thousand CSCL centerline records). A five-borough build therefore must not widen the old bounded Flatiron query and assume a single response is complete.

`nydrive_map_compiler.acquisition` downloads stable Socrata pages using explicit `$limit`, `$offset`, and `$order` values, then sorts the compact snapshot deterministically before compilation. Large raw snapshots are generated locally and should not be committed to Git.

```bash
python3 tools/map_compiler/scripts/acquire_citywide_snapshot.py \
  --output data/raw/nyc-five-boroughs.json \
  --roadbed-revision 2024-04-24 \
  --centerline-revision 2026-08-16
```

Record the revision actually fetched. Do not silently retain the example dates after a source refresh.

## Citywide centerline identity

A bare CSCL `PHYSICALID` is not treated as a safe five-borough identity. The adapter prefers official `BPHYS_ID`; when it is absent it prefixes `PHYSICALID` with the borough code. Old bounded fixtures that contain neither borough field retain their historic ID so existing deterministic fixture output remains readable.

The compiler also carries normalized borough names on every centerline when the official borough code is available.

## Elevation-enabled compile

The citywide build is schema v2 and requires the T010 elevation path. Pass every required 2017 NYC LiDAR bare-earth DEM GeoTIFF to the compiler:

```bash
python3 tools/map_compiler/scripts/compile_citywide.py \
  --snapshot data/raw/nyc-five-boroughs.json \
  --output build/nyc-five-boroughs \
  --dem data/dem/tile-01.tif \
  --dem data/dem/tile-02.tif
```

Repeat `--dem` for the complete DEM coverage used by the build. The compiler will not substitute a flat citywide surface when DEM data is omitted.

The output directory contains:

- `manifest.json` — coordinate/source metadata, tile index, per-tile byte counts and SHA-256 digests, vertical diagnostics, and the aggregate citywide audit;
- `tiles/*.json` — deterministic 256 m runtime tiles;
- `citywide_audit.json` — a standalone copy of topology/connectivity findings for review and CI artifacts.

## Connectivity audit contract

The road graph is built from source-derived CSCL path endpoints. Endpoints may snap within 0.75 m, but **only when their resolved NYC vertical level agrees**. This prevents a coincident bridge/elevated endpoint from becoming connected to an at-grade road solely because X/Y positions match.

The audit reports:

- coverage/counts for Manhattan, the Bronx, Brooklyn, Queens, and Staten Island;
- total graph nodes/edges and connected components;
- fraction of edges in the largest component plus a sample of roads outside it;
- cross-borough connection nodes and borough-pair counts;
- roads spanning multiple runtime tiles;
- bridge/ramp/tunnel/at-grade structure counts;
- duplicate stable IDs and invalid/degenerate centerlines;
- unresolved Roadbed vertical associations and other T010 vertical diagnostic codes;
- missing tile files after writing the build.

These are diagnostics, not an instruction to hide source problems. A disconnected component or unresolved vertical structure remains visible for a later correction task.

## Representative route audits

The default audit set anchors real cross-borough crossings:

| Audit | Boroughs |
| --- | --- |
| Brooklyn Bridge | Manhattan ↔ Brooklyn |
| Queensboro Bridge | Manhattan ↔ Queens |
| Macombs Dam Bridge | Manhattan ↔ Bronx |
| Bronx–Whitestone Bridge | Queens ↔ Bronx |
| Verrazzano-Narrows Bridge | Brooklyn ↔ Staten Island |

Waypoints are snapped to the nearest compiled graph node within a bounded distance. The audit first proves structural connectivity and separately checks whether the requested waypoint order is traversable with source traffic direction. This separation keeps a one-way-data problem distinguishable from a physically disconnected map.

## Verification

The task-level verification command is:

```bash
python3 -m pytest tools/map_compiler/tests
```

The suite includes a deterministic synthetic five-borough world with cross-tile and cross-borough links, bridge/ramp/tunnel level transitions, vertical-level-safe endpoint snapping, duplicate/missing-borough diagnostics, and paginated acquisition behavior. Live source acquisition is an additional integration check, not a replacement for deterministic tests.
