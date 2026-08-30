# Ny-drive map source policy

The browser must never parse raw GIS files. This directory is the offline boundary where source data is acquired, normalized into metres, validated, and later compiled into game tiles.

## Coordinate contract

- **Project CRS:** EPSG:32118 — NAD83 / New York Long Island, metres.
- **Fixed project origin:** WGS84 `(-74.0060, 40.7128)`. The projected coordinate of this point is subtracted from every normalized point, so `(0, 0)` is stable and reproducible.
- **NYC DCM native CRS:** EPSG:2263 — NAD83 / New York Long Island (US survey feet). DCP metadata identifies EPSG:2263 explicitly; mapped street width is treated as feet and converted to metres.
- **NYC Open Data / Socrata GeoJSON and OSM:** WGS84 longitude/latitude (EPSG:4326) unless an input explicitly declares another CRS.

Do not silently guess the CRS for full File Geodatabase imports. The API adapters have explicit defaults; future FGDB readers must pass the CRS discovered from the source layer metadata.

## Pinned sources

Machine-readable acquisition metadata lives in `sources.lock.json`. Large citywide source archives are deliberately **not committed**.

### NYC Planimetric Database — Roadbed

Dataset ID: `i36f-5ih7`. The source supplies polygon/multipolygon roadbed geometry with `SOURCE_ID`, `FEAT_CODE`, `SUB_CODE`, and `STATUS`. The Socrata GeoJSON adapter consumes WGS84 geometry and preserves source fields/provenance.

The portal listed metadata updated 2025-12-10 and data updated 2024-04-24 when this source lock was written. Before a citywide rebuild, record the actual fetched revision in the build manifest rather than assuming the portal has not changed.

### Digital City Map — Street Center Line

Dataset resource: `eak9-f97n`. DCP describes the feature class as citywide official street centerlines and widths. Its metadata identifies native EPSG:2263 and fields including `OBJECTID`, `Borough`, `Feat_Type`, `Street_NM`, `Route_Type`, mapped street width, roadway type, and build status. Current shapefile metadata exposes the ten-character DBF field name `Streetwidt`; older FGDB/exports may expose `Streetwidth`, so the adapter deliberately supports both aliases.

DCM updates monthly. `sources.lock.json` pins the DCP metadata release dated 2025-10-31 for the current normalization contract. A later deliberate source refresh should update the lock and regenerate fixtures/build manifests in the same change.

### OpenStreetMap

The adapter consumes ordinary Overpass JSON (`node` + `way` elements) and normalizes road semantics from tags such as `highway`, `oneway`, `lanes`, `lanes:forward`, `lanes:backward`, `width`, `bridge`, `tunnel`, and `layer`. The tiny committed fixture is a deterministic schema snapshot; it is not copied real-world geometry.

For development-sized extracts, use Overpass. A citywide production ingest should use a reproducible `.osm.pbf` extract and feed equivalent way/node records to this normalized boundary rather than make tens of thousands of Overpass requests.

## Acquisition examples

Roadbed API snapshot for a bounded experiment:

```bash
curl -L 'https://data.cityofnewyork.us/resource/i36f-5ih7.geojson?$limit=1000' -o data/raw/roadbed-sample.geojson
```

DCM source archives are downloaded from the NYC Open Data resource page named in `sources.lock.json`. Preserve the downloaded filename, retrieval timestamp, byte size, and SHA-256 in the build manifest; do not commit the archive itself.

OSM development extract (example Overpass query body):

```text
[out:json][timeout:60];
way[highway](40.70,-74.02,40.73,-73.98);
(._;>;);
out body;
```

## Terms and attribution

NYC Open Data states that Open Data has no usage restrictions, while its Terms of Use and DCP metadata include accuracy/fitness disclaimers and allow provider-specific additional terms. Record NYC sources and revisions in distributed data notices even where attribution is not mechanically required.

OpenStreetMap data is ODbL 1.0. Any public build using OSM-derived data must visibly credit **© OpenStreetMap contributors** and make the ODbL availability clear. Keep OSM provenance separate from NYC-source provenance so a future compiler can determine which derived attributes came from which database.

## Python dependency notices

- pyproj 3.7.2 — MIT; wraps PROJ.
- Shapely 2.1.2 — BSD-3-Clause; uses GEOS (LGPL-2.1-or-later).
- pytest 9.0.2 — MIT; test-only.

These are compiler dependencies only and are not shipped to the browser.
