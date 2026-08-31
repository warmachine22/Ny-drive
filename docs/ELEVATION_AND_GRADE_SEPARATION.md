# Elevation and grade separation

T010 introduces the first source-derived vertical road topology for Ny-drive. The goal is not to pretend every deck height is surveyed perfectly; the goal is to preserve real ground grade where authoritative terrain exists and prevent roads that cross at different levels from becoming false flat intersections.

## Tile schema v2

Schema-v2 road geometry extends the existing horizontal tile-local point format:

```text
[local_x_m, local_y_m, elevation_m]
```

`local_x_m` and `local_y_m` remain coordinates within the 256 m logical tile. `elevation_m` is a project-wide NAVD88-based vertical value in metres and is not floating-origin rebased.

Schema-v1 fixtures remain supported and implicitly use elevation `0 m`. This keeps the existing flat development fixture usable while real elevation datasets are compiled separately.

## Source roles

- **NYC Roadbed polygons remain the authoritative road footprint.** T010 does not replace them with centerline ribbons.
- **2017 NYC LiDAR bare-earth DEM** supplies terrain/ground grade. It is a bare-earth source and therefore must not be treated as bridge-deck geometry.
- **NYC CSCL vertical level codes** supply strong official evidence for above-grade, at-grade, and below-grade road endpoints. Level 13 is at grade; lower values are below grade and higher values are above grade.
- **NYC segment type** identifies bridge, tunnel, and ramp segments where present.
- **OpenStreetMap** supplements missing semantics with `bridge`, `tunnel`, numeric `layer`, and link-road/ramp-like classifications.

The compiler retains source provenance so a future correction can distinguish official topology from supplemental or inferred values.

## Vertical profile construction

At-grade roads sample the bare-earth DEM along their vertices.

Structured roads cannot simply follow the terrain below them. For a bridge, tunnel, elevated road, or ramp, the compiler:

1. samples terrain at the path endpoints;
2. interpolates the terrain baseline continuously along the path;
3. resolves relative endpoint levels from official NYC codes when available, otherwise from OSM `layer`, otherwise from structural semantics;
4. interpolates the level along ramps or other level-changing segments;
5. adds the resolved level separation to the baseline.

This creates a continuous driving profile across ordinary slopes and tile seams while preserving separation at overpasses and tunnel crossings.

## Uncertainty policy

Not all source records contain a surveyed deck or tunnel depth. When only bridge/tunnel semantics are known, the current implementation uses `5.0 m` per inferred level to keep the topology separated. The compiler emits `inferred-structure-clearance` for those cases.

That fallback is deliberately **not** presented as exact real-world clearance. It is a temporary, explicit uncertainty until stronger source data or a structure-specific correction rule is available.

Contradictions are also surfaced instead of flattened. Examples include:

- a feature simultaneously marked bridge and tunnel;
- a bridge carrying below-grade numeric levels;
- a tunnel carrying above-grade numeric levels;
- missing DEM samples;
- one Roadbed polygon substantially overlapping centerlines at contradictory vertical levels.

The last case emits `ambiguous-roadbed-vertical-topology`. An unresolved Roadbed surface is omitted from collision/render geometry rather than becoming a false driveable intersection.

## Runtime behavior

The browser runtime reads schema-v2 elevation directly into Three.js and Rapier geometry. Roadbed remains one static trimesh per physics-active tile, preserving the streaming/collider architecture from T005.

Centerline debug geometry follows the compiled height profile. Safe reset poses also carry elevation, and stacked roads can be disambiguated using both horizontal distance and the vehicle's current height.

Fall recovery is relative to the selected road elevation rather than an absolute world `y = -5 m` threshold, so a legitimate below-grade tunnel does not look like an unrecoverable fall.

## Relationship to T017 support ground

T017's flat non-road support is a schema-v1 prototype aid only. **Schema-v2 elevation tiles never create the flat support slab.** This prevents an artificial plane from cutting through tunnels, filling the space below bridges, or defeating real terrain/grade separation.

Future terrain work may add source-derived non-road terrain meshes. That should be a separate streamed geometry layer and must preserve the same vertical topology rules rather than re-enable the prototype flat support.

## Validation expectations

Elevation/grade changes should include deterministic fixtures that verify:

- vertical samples and unit conversion are in metres;
- bridge and tunnel paths crossing at the same XY position remain vertically distinct;
- ramp profiles interpolate continuously between endpoint levels;
- tile seams preserve the same elevation on both sides;
- ambiguous vertical topology produces diagnostics;
- unresolved geometry is not silently converted into collision surfaces.
