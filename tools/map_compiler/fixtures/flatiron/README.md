# Flatiron / Madison Square development fixture

This is Ny-drive's first real NYC road-tile fixture. It covers roughly Fifth Avenue through Park Avenue South and East 20th through East 28th Streets, including the Flatiron/Madison Square street grid.

## Inputs

`source_snapshot.json` is a small, checked-in, bounded snapshot from official NYC Open Data:

- NYC Planimetric Roadbed (`i36f-5ih7`): 110 clipped roadbed polygons.
- NYC Street Centerline / CSCL (`inkn-q76z`): 71 clipped street segments with traffic direction, roadway class, travel/parking lane counts, level codes, and street names where published.

The source snapshot uses WGS84 coordinates and records the exact source query URLs/revisions. It exists so normal development and tests do not depend on live NYC APIs.

To deliberately refresh the snapshot:

```bash
python3 tools/map_compiler/scripts/acquire_flatiron_fixture.py \
  --output tools/map_compiler/fixtures/flatiron/source_snapshot.json
```

A refresh is a source-data change and should be reviewed rather than happening automatically.

## Compiled runtime data

`compiled/manifest.json` and `compiled/tiles/*.json` are deterministic runtime output generated from the snapshot:

```bash
python3 tools/map_compiler/scripts/compile_flatiron_fixture.py
```

Current output contains 15 logical tiles. Each tile is 256 m square in EPSG:32118-derived project coordinates and stores geometry in tile-local metres. Roadbed polygons can be consumed as visual/drivable surfaces, while centerlines carry stable IDs and driving metadata. A feature clipped across multiple tiles keeps the same stable ID in every tile.

The browser does not need pyproj, Shapely, Socrata, or any GIS parser to load these files.

## Verification

```bash
python3 -m pytest tools/map_compiler/tests -k 'tile or seam or fixture'
```

The seam tests split geometry across 256 m boundaries, reconstruct it in global coordinates, and verify that polygon area/centerline length is preserved without gaps. The real-fixture tests also enforce deterministic output and tile-local coordinate bounds.
