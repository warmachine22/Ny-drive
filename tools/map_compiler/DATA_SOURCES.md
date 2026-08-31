# Ny-drive map source policy

The browser must never parse raw GIS files. This directory is the offline boundary where source data is acquired, normalized into metres, validated, and later compiled into game tiles.

## Coordinate contract

- **Project CRS:** EPSG:32118 — NAD83 / New York Long Island, metres.
- **Fixed project origin:** WGS84 `(-74.0060, 40.7128)`. The projected coordinate of this point is subtracted from every normalized horizontal point, so `(0, 0)` is stable and reproducible.
- **NYC DCM native CRS:** EPSG:2263 — NAD83 / New York Long Island (US survey feet). DCP metadata identifies EPSG:2263 explicitly; mapped street width is treated as feet and converted to metres.
- **NYC Open Data / Socrata GeoJSON and OSM:** WGS84 longitude/latitude (EPSG:4326) unless an input explicitly declares another CRS.
- **2017 NYC LiDAR bare-earth DEM:** horizontal EPSG:6539 and vertical EPSG:6360 (NAVD88 height in US survey feet) in the NOAA-distributed GeoTIFF product. The compiler reprojects horizontally and converts vertical values to metres.

Do not silently guess the CRS for full File Geodatabase or raster imports. The API adapters have explicit defaults; future FGDB readers must pass the CRS discovered from source layer metadata, and DEM readers must reject rasters with no declared CRS.

## Pinned sources

Machine-readable acquisition metadata lives in `sources.lock.json`. Large citywide source archives are deliberately **not committed**.

### NYC Planimetric Database — Roadbed

Dataset ID: `i36f-5ih7`. The source supplies polygon/multipolygon roadbed geometry with `SOURCE_ID`, `FEAT_CODE`, `SUB_CODE`, and `STATUS`. The Socrata GeoJSON adapter consumes WGS84 geometry and preserves source fields/provenance.

The portal listed metadata updated 2025-12-10 and data updated 2024-04-24 when this source lock was written. Before a citywide rebuild, record the actual fetched revision in the build manifest rather than assuming the portal has not changed.

### Digital City Map / CSCL street centerlines

The compiler uses official NYC street-centerline attributes for topology and road semantics. The source exposes traffic direction, lane counts, street widths, segment type, and vertical endpoint level codes.

For vertical topology, NYC level code `13` is at grade, `1` through `12` are successively below grade, and `14` through `26` are successively above grade. Segment type also identifies structures including bridge (`3`), tunnel (`4`), and ramp (`9`). These official level/structure semantics take precedence over weaker inferred vertical information when present.

DCM/CSCL updates periodically. Preserve the exact source revision used for a build and do not silently combine records from different releases.

### 2017 NYC LiDAR bare-earth DEM

T010 selects the City of New York's 2017 LiDAR-derived **hydro-flattened bare-earth DEM** as the initial authoritative ground-elevation baseline. NOAA Office for Coastal Management mirrors the NYC-produced DEM as public GeoTIFFs under dataset 9307, which provides a stable bulk-download path for reproducible offline builds.

The product is a one-foot grid in New York Long Island State Plane coordinates, with NAVD88 (Geoid12B) elevations in US survey feet. `RasterElevationSampler` reprojects sample locations into each raster's declared CRS and converts vertical samples to metres before tile compilation.

This is a **bare-earth** product. It is authoritative for terrain/ground grade, not for bridge decks, elevated viaduct decks, or tunnel driving surfaces. The compiler therefore combines terrain with NYC centerline level codes and OSM structure semantics instead of draping every road directly onto the DEM.

The 2017 capture date is a known temporal limitation. A later deliberate elevation-source refresh should update `sources.lock.json`, regenerate representative fixtures, and record the new source revision rather than silently changing city elevation underneath existing compiled data.

### OpenStreetMap

The adapter consumes ordinary Overpass JSON (`node` + `way` elements) and normalizes road semantics from tags such as `highway`, `oneway`, `lanes`, `lanes:forward`, `lanes:backward`, `width`, `bridge`, `tunnel`, and `layer`. Link-road classes such as `*_link` are also useful ramp evidence. The tiny committed fixture is a deterministic schema snapshot; it is not copied real-world geometry.

For development-sized extracts, use Overpass. A citywide production ingest should use a reproducible `.osm.pbf` extract and feed equivalent way/node records to this normalized boundary rather than make tens of thousands of Overpass requests.

OSM supplements official NYC geometry/topology; it does not replace authoritative Roadbed surfaces or stronger NYC vertical level codes blindly.

## Vertical topology policy

The initial source priority is:

1. official NYC numeric endpoint level codes when present;
2. OSM numeric `layer` where official levels are unavailable;
3. bridge/tunnel/ramp semantics as structural evidence;
4. bare-earth DEM for ground grade.

For structured segments, the compiler interpolates a continuous profile between terrain at the segment endpoints and then applies the resolved vertical level. This deliberately prevents a bridge deck from sagging onto the bare-earth terrain underneath it or a tunnel from becoming a flat surface intersection.

A bridge or tunnel may have at-grade endpoint codes even though its interior must be separated from a crossing. When bridge/tunnel semantics require interior separation but no stronger numeric offset is available, the compiler keeps the endpoints on their terrain grade and uses a provisional continuous mid-span clearance/depth envelope with a maximum magnitude of `5.0 m`. It emits `inferred-structure-clearance`. **That number is a topology-preserving fallback, not a claim that the real deck clearance or tunnel depth is exactly five metres.** Difficult structures can later receive stronger source data or explicit correction rules.

Schema-v2 polygon/path output is sampled at bounded spacing so the continuous height profile is represented in compiled geometry even when source segments have sparse vertices.

When one Roadbed polygon overlaps comparably strong centerlines at contradictory vertical topologies, the compiler reports `ambiguous-roadbed-vertical-topology` rather than choosing a flat crossing silently. Schema-v2 runtime code does not create collision geometry for unresolved Roadbed surfaces. Per-tile diagnostics are scoped to features in that tile so citywide warnings are not copied into every streamed payload.

## Acquisition examples

Roadbed API snapshot for a bounded experiment:

```bash
curl -L 'https://data.cityofnewyork.us/resource/i36f-5ih7.geojson?$limit=1000' -o data/raw/roadbed-sample.geojson
```

DEM archives are not committed. Download the required 2017 NYC bare-earth GeoTIFFs from the bulk location pinned in `sources.lock.json`, preserve their filenames, retrieval timestamps, byte sizes, and SHA-256 values in the build manifest, and pass the local paths to `RasterElevationSampler`.

OSM development extract (example Overpass query body):

```text
[out:json][timeout:60];
way[highway](40.70,-74.02,40.73,-73.98);
(._;>;);
out body;
```

## Terms and attribution

NYC Open Data states that Open Data has no usage restrictions, while its Terms of Use and DCP metadata include accuracy/fitness disclaimers and allow provider-specific additional terms. Record NYC sources and revisions in distributed data notices even where attribution is not mechanically required.

NOAA metadata for the 2017 NYC DEM reports no access constraints. Keep City/NOAA provenance and the source revision in build manifests so the elevation product remains auditable.

OpenStreetMap data is ODbL 1.0. Any public build using OSM-derived data must visibly credit **© OpenStreetMap contributors** and make the ODbL availability clear. Keep OSM provenance separate from NYC-source provenance so a future compiler can determine which derived attributes came from which database.

## Python dependency notices

- pyproj 3.7.2 — MIT; wraps PROJ.
- rasterio 1.4.3 — BSD-3-Clause; wraps GDAL for compiler-side raster access.
- Shapely 2.1.2 — BSD-3-Clause; uses GEOS (LGPL-2.1-or-later).
- pytest 9.0.2 — MIT; test-only.

These are compiler dependencies only and are not shipped to the browser.
