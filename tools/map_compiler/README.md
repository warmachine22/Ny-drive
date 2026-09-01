# Ny-drive map compiler

Offline GIS normalization and deterministic world compilation for Ny-drive.

## Setup

```bash
python3 -m pip install -e 'tools/map_compiler[test]'
python3 -m pytest tools/map_compiler/tests
```

## Boundary

Input adapters cover:

- NYC Planimetric Roadbed GeoJSON polygons;
- NYC CSCL street-centerline GeoJSON and its lane, direction, borough, structure, and vertical-level metadata;
- OSM road ways and supplemental lane/direction/grade-separation semantics;
- the 2017 NYC LiDAR-derived bare-earth DEM for source-derived elevation.

Every adapter normalizes into plain Python dataclasses in local **metres**. Raw GIS parsing, projections, source field names, DEM access, and OSM tags stay on the compiler side; the browser loads deterministic 256 m runtime tiles only.

## Development fixture

The bounded Flatiron snapshot remains the fast reproducible vertical slice:

```bash
python3 tools/map_compiler/scripts/compile_flatiron_fixture.py
```

## Five-borough build

T012 adds paginated citywide acquisition, schema-v2 compilation, tile checksums, connectivity diagnostics, and representative cross-borough route audits:

```bash
python3 tools/map_compiler/scripts/acquire_citywide_snapshot.py \
  --output data/raw/nyc-five-boroughs.json

python3 tools/map_compiler/scripts/compile_citywide.py \
  --snapshot data/raw/nyc-five-boroughs.json \
  --output build/nyc-five-boroughs \
  --dem data/dem/first.tif \
  --dem data/dem/second.tif
```

See `CITYWIDE_BUILD.md`, `DATA_SOURCES.md`, and `sources.lock.json` for the citywide audit contract, source provenance, and acquisition rules.
