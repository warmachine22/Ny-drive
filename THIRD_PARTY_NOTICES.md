# Third-party notices

Ny-drive records direct software dependencies here so later release work can preserve attribution and license obligations. Exact versions are pinned in `package.json` and `tools/map_compiler/pyproject.toml`.

## Browser runtime

| Package | Version | License | Purpose |
| --- | ---: | --- | --- |
| `three` | 0.185.1 | MIT | Browser 3D rendering and runtime procedural building massing |
| `@dimforge/rapier3d-compat` | 0.20.0 | Apache-2.0 | WebAssembly rigid-body physics |

## Browser development

| Package | Version | License | Purpose |
| --- | ---: | --- | --- |
| `@types/three` | 0.185.4 | MIT | TypeScript declarations for Three.js |
| `typescript` | 7.0.2 | Apache-2.0 | Static type checking |
| `vite` | 8.2.2 | MIT | Development server and production bundling |
| `vitest` | 4.1.11 | MIT | Unit tests |

## Map compiler

| Package | Version | License | Purpose |
| --- | ---: | --- | --- |
| `pyproj` | 3.7.2 | MIT | CRS definitions and coordinate transformations via PROJ |
| `shapely` | 2.1.2 | BSD-3-Clause | Geometry normalization via GEOS |
| `pytest` | 9.0.2 | MIT | Map-compiler tests (development only) |

PROJ is MIT licensed. GEOS is LGPL-2.1-or-later.

## Geographic data

| Dataset | Provider | Use in Ny-drive | Terms / attribution |
| --- | --- | --- | --- |
| NYC Building Footprints (`5zhs-2jue`) | NYC Office of Technology and Innovation / NYC Open Data | Real building perimeters and available roof heights for simplified procedural city massing | NYC Open Data policies and restrictions apply; credit NYC OTI / NYC Open Data |

The complete geographic-source pins, revisions, transforms, and source-specific notes are tracked in `tools/map_compiler/DATA_SOURCES.md` and `tools/map_compiler/sources.lock.json` because source-data obligations are not the same as software-library licenses.

No external procedural art package or third-party building-model asset is used by the T011 massing system; it generates simple geometry from NYC footprints with the existing Three.js dependency.

Before a public game release, generate and review the complete transitive dependency license inventory and add required attribution text/assets for geographic data and vehicle/art assets.
