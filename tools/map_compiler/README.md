# Ny-drive map compiler

Offline GIS normalization for the Ny-drive world pipeline.

## Setup

```bash
python3 -m pip install -e 'tools/map_compiler[test]'
python3 -m pytest tools/map_compiler/tests
```

## Boundary

Input adapters currently cover:

- NYC Planimetric Roadbed GeoJSON polygons;
- NYC DCM Street Center Line GeoJSON exported in native EPSG:2263 (or another explicitly supplied CRS);
- OSM Overpass JSON road ways and their lane/direction/grade-separation semantics.

Every adapter emits plain Python dataclasses in local **metres**. Raw GIS parsing, projections, source field names, and OSM tags stay on the compiler side. Runtime/tile serialization comes in later tasks.

See `DATA_SOURCES.md` and `sources.lock.json` for pinned data provenance and acquisition rules.
