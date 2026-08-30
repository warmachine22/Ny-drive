# Plan

Status: READY

This is the current implementation strategy for the accepted product intent in `PRODUCT.md`. Keep it current when consequential technical strategy changes. Do not use it as a progress diary.

## Technical Approach

Ny-drive will be built as two deliberately separate systems:

1. **Offline geographic compiler** — a Python pipeline ingests authoritative NYC GIS data plus OpenStreetMap and elevation data, normalizes everything into a common meter-based coordinate system, resolves road semantics and grade separation, partitions the city into deterministic world tiles, triangulates game-ready geometry, and emits compact runtime assets plus provenance/attribution metadata.
2. **Browser driving runtime** — a TypeScript application uses Three.js for rendering and Rapier 3D/WASM for rigid-body physics. It streams only nearby compiled tiles, maintains a floating local origin, creates physics colliders only for the active driving region, and runs one physics-driven AWD car with an isometric/near-isometric follow camera.

The first implementation milestone is a vertical slice covering roughly 20–30 real Manhattan blocks. That slice must prove the entire path from source GIS data to browser road geometry, streaming, collision, vehicle handling, camera, and reset before the compiler is expanded citywide. The project should not hand-author roads in Three.js scenes.

### Rendering baseline

Use Three.js with **WebGLRenderer/WebGL2 as the initial compatibility baseline**. Three.js `WebGPURenderer` is a promising future optimization and can fall back to WebGL2, but it remains experimental as of planning. Runtime interfaces should avoid unnecessary renderer-specific coupling so a later migration or opt-in WebGPU path remains practical.

### Coordinate model

- Source datasets may arrive in different projections/units; the compiler converts them into a single projected CRS expressed in meters (initially UTM zone 18N / EPSG:32618 unless validation identifies a more suitable NYC-local metric CRS).
- The compiler subtracts a fixed NYC project origin so stored world coordinates are meter-based and reasonably small.
- World tiles use deterministic meter-aligned origins; geometry inside each tile is stored tile-local.
- The browser maintains a floating runtime origin and rebases loaded tiles around the vehicle when necessary. Geographic identity remains in immutable world/tile coordinates so rebasing never changes real distances.

### Tile strategy

Start with a **256 m × 256 m logical tile grid**. The exact active radius is a tunable runtime parameter rather than an architectural constant.

Prototype output may use a simple manifest plus GLB/JSON assets:

- visual road/scenery meshes as GLB or compact binary geometry;
- semantic metadata (road IDs, lane/direction data, source provenance, grade/layer information) in JSON;
- collision geometry derived from or emitted alongside the road mesh;
- one citywide tile index/manifest describing bounds, versions, checksums, attribution, and neighboring tiles.

If request count or decode overhead becomes material, the same logical tile format can later be packed into larger bundles without changing gameplay systems.

### Vehicle simulation

Use one dynamic Rapier rigid-body chassis with a custom raycast/shape-cast wheel model rather than kinematic car movement. The initial model should use:

- four independently sampled wheel contacts;
- spring/damper suspension;
- longitudinal drive/brake force;
- lateral tire force based on slip angle with a tunable grip-to-slide curve;
- configurable AWD torque distribution and differential-like traction behavior;
- chassis mass/inertia and load-transfer effects sufficient to make weight movement matter;
- a fixed physics step, initially targeting 120 Hz with profiling before increasing it;
- handbrake behavior that directly changes rear-wheel braking/grip so it can initiate or tighten rotation;
- driving assists/tuning layered on top of physical forces to keep slides recoverable and fun.

Exact factory GC8 parameters are not required to block the first physics implementation. All important vehicle values should be data-driven so later research and licensed assets can refine them.

## Architecture / Components

### `tools/map_compiler`

Responsibilities:

- acquire/import pinned snapshots of source data without committing giant raw datasets to Git;
- normalize CRS and units;
- reconcile NYC roadbed/centerline geometry with OSM attributes such as lanes, oneway, road class, bridge, tunnel, and layer;
- build a road graph and driveable surface representation;
- sample/attach elevation and construct grade-separated geometry;
- clip/partition features into deterministic tiles with seam-safe boundaries;
- triangulate road, terrain, and building geometry;
- emit manifests, runtime assets, diagnostics, and attribution/provenance records;
- run dataset-quality and connectivity checks before citywide publication.

The compiler must be deterministic for the same pinned inputs and configuration.

### `src/world`

Responsibilities:

- load the city/tile manifest;
- determine visible and physics-active tile rings around the player;
- asynchronously load/decode tiles;
- attach/detach Three.js objects and Rapier colliders;
- maintain tile cache and lifecycle states;
- perform floating-origin rebases without changing geographic/world identity;
- expose road/surface queries needed for vehicle reset and debugging.

### `src/vehicle`

Responsibilities:

- chassis rigid body and collider setup;
- suspension queries;
- tire force calculation and AWD power/braking distribution;
- handbrake/drift behavior;
- tunable vehicle configuration;
- lightweight telemetry useful for tuning slip, speed, wheel contact, steering, and force behavior.

### `src/input`

Provide action-based input (`steer`, `throttle`, `brake/reverse`, `handbrake`, `reset`) rather than hard-coding key checks into vehicle physics. Keyboard is required initially; this boundary allows later gamepad/wheel support without rewriting the car.

### `src/camera`

Near-isometric follow camera with smoothing, speed-sensitive look-ahead, configurable pitch/yaw/zoom, and obstruction-safe behavior if needed. It consumes vehicle state but does not own physics.

### `src/render`

Three.js renderer initialization, scene lighting/material conventions, instancing/batching helpers, debug overlays, and renderer capability selection. Keep material complexity low until representative NYC tiles have been profiled.

### `src/game`

Thin orchestration layer for startup, fixed-step physics accumulation, render interpolation, reset flow, spawn selection, and subsystem lifetime. Game logic should remain small because the accepted initial mode is free driving.

### Data flow

`NYC GIS + OSM + elevation -> compiler normalization -> road graph/geometry -> tile assets + manifest -> browser tile streamer -> Three.js meshes + Rapier colliders -> vehicle physics/camera/input`

Raw GIS parsing must never be required in the browser.

## Project Structure

Expected structure after the first implementation tasks:

```text
.
├── src/
│   ├── game/
│   ├── render/
│   ├── world/
│   ├── vehicle/
│   ├── input/
│   ├── camera/
│   └── debug/
├── public/
│   └── world/                 # generated/sample runtime tiles; large city builds may be external artifacts
├── tools/
│   └── map_compiler/
│       ├── nyc_drive/
│       │   ├── sources/
│       │   ├── normalize/
│       │   ├── roads/
│       │   ├── elevation/
│       │   ├── tiles/
│       │   └── validation/
│       ├── tests/
│       └── pyproject.toml
├── tests/
│   ├── unit/
│   └── browser/
├── data/
│   ├── README.md              # acquisition instructions, licenses, pinned source versions
│   └── fixtures/              # small redistributable compiler fixtures only
├── docs/
│   ├── DATA_SOURCES.md
│   ├── VEHICLE_MODEL.md
│   └── WORLD_FORMAT.md
├── .agent/
├── package.json
├── tsconfig.json
└── vite.config.ts
```

Generated citywide data should not be committed blindly to Git if size makes that impractical. Development fixtures and a small playable slice belong in-repo or in deterministic downloadable artifacts so tests remain reproducible.

## Dependencies / Integrations

### Browser runtime

- **TypeScript** — primary client language.
- **Vite** — development/build tooling.
- **Three.js** — scene/rendering foundation; begin with WebGL2 baseline.
- **@dimforge/rapier3d-compat** (or the current supported Rapier JS/WASM package selected during implementation) — rigid bodies, colliders, and scene queries.
- **glTF/GLB loading** through Three.js where the prototype tile format uses GLB.
- A small test stack such as **Vitest** for deterministic client/unit tests and **Playwright** for browser smoke tests once the first runnable slice exists.

Versions must be pinned by the scaffold task rather than copied from this planning document.

### Map compiler

Python 3.12+ with a `pyproject.toml`-managed environment. Expected libraries include:

- `pyproj` for CRS conversion;
- `shapely` for geometry operations;
- `pyogrio`/GeoPandas or equivalent for NYC GIS import;
- `osmium`/pyosmium or an equivalent reliable OSM PBF reader;
- `numpy` for geometry/numeric processing;
- `rasterio` or equivalent for raster DEM/elevation inputs when selected;
- a deterministic polygon triangulation library such as Mapbox Earcut where needed.

Avoid making raw PDAL/LiDAR processing a mandatory browser-development dependency unless T010 proves it necessary; prefer a practical DEM/elevation preprocessing path first.

### Geographic sources

Preferred source hierarchy:

1. Official NYC datasets for NYC-specific geometry where authoritative and usable, including current street centerline/roadbed or planimetric products and Building Footprints.
2. OpenStreetMap for lane counts/structure, oneway semantics, road hierarchy, bridges, tunnels, and `layer` relationships where NYC datasets do not directly encode the needed game semantics.
3. An authoritative NYC or compatible elevation/DEM source selected and pinned during the grade-separation task.

Every compiled release must carry source names, snapshot dates/versions where available, license/attribution text, and transformation provenance. OSM-derived distributions must preserve required OpenStreetMap attribution and database-license obligations. Dataset licensing must be reviewed before any public/commercial distribution.

### Vehicle/art assets

The physics prototype should use original/simple placeholder geometry or an asset with explicit redistribution rights. Exact Subaru logos, badges, trademarks, and third-party GC8 meshes are not assumed licensed. The runtime vehicle configuration should not depend on branded mesh naming so a licensed model can be substituted later.

## Verification Strategy

Verification is layered so map correctness, physics correctness, and browser integration can fail independently and be diagnosed cheaply.

### Planning/bootstrap health

Until T002 installs product tooling, `.agent/VERIFY.json` uses the repository's existing Roach checks as the required quick command. T002 must replace/extend this with product-aware commands once `package.json` and compiler tests exist.

### Compiler tests

- unit tests for projection, unit conversion, clipping, polygon repair, graph construction, lane/direction normalization, tile addressing, and seam handling;
- fixed small geographic fixtures with expected bounds/lengths/connectivity;
- assertions that generated distances remain one-to-one in meters within defined source/projection tolerance;
- diagnostics for disconnected road components, duplicate/overlapping road surfaces, impossible elevations, and grade-separated crossings incorrectly joined;
- reproducibility checks using pinned fixture inputs and deterministic manifests/checksums.

### Client/unit tests

- tile state-machine/load-unload tests;
- floating-origin transform invariants;
- fixed-step accumulator tests;
- vehicle force/tire curve tests that do not require rendering;
- reset-road query behavior;
- input action mapping tests.

### Browser smoke tests

Once runnable, Playwright should verify that a production build loads, WebGL2 initializes, a known fixture tile becomes ready, the vehicle enters the simulation, controls change vehicle state, reset works, and no fatal console errors occur.

### Capability-dependent verification

Driving feel, camera readability, recognizable spatial character, drift recoverability, seam visual quality, and performance hitching require human/browser interaction in addition to automated checks. Tasks that depend on those qualities must record what was actually observed rather than claiming an automated test proves subjective feel.

### Performance gates

Do not set a launch hardware floor before profiling the representative slice. T014 will establish measured targets. At minimum, profiling must record frame time, physics time, loaded tile count, collider count, JS/WASM memory trend, and tile-load hitching during a long route. Memory after leaving an area must return toward a bounded steady state rather than grow with total distance traveled.

## Risks / Unknowns

1. **Roadbed/lane reconciliation:** NYC geometry and OSM semantics may disagree. Preserve provenance and confidence; do not silently invent precision. The compiler should prefer authoritative roadbed geometry for surface shape while attaching OSM semantic attributes only when matching is credible.
2. **Grade separation is the highest map risk:** elevated highways, ramps, bridges, and tunnels require both topology and elevation. T010 exists before citywide expansion specifically to solve representative complex cases.
3. **Tile seams:** polygon clipping and collider boundaries can create cracks or duplicate surfaces. Build seam fixtures before scaling to five boroughs.
4. **Physics feel:** realistic-looking equations can still produce a bad driving game. Keep tire/suspension parameters data-driven, instrument them, and tune on the Manhattan slice before citywide work dominates attention.
5. **Browser/WASM performance:** Rapier raycasts and triangle-mesh colliders are viable for a single car but active collision geometry must stay bounded. Separate visible and physics tile radii if profiling requires it.
6. **Dataset size:** citywide building footprints and road meshes may be large. The compiler should support LOD/feature simplification and optional external artifact hosting; runtime APIs must not assume every tile is packaged into the JavaScript bundle.
7. **Source licenses and trademarks:** technical feasibility does not grant redistribution rights. T013 creates an explicit asset/data attribution gate before release validation.
8. **Renderer evolution:** WebGPU support is improving but not necessary for the first milestone. Avoid making accepted product behavior depend on an experimental renderer.
9. **Exact GC8 specification:** model years/markets differ. The first car should feel like a light turbo AWD rally-derived sedan; exact gear ratios, torque split, mass distribution, tires, and branded art can be refined from reliable sources without redesigning the physics architecture.

## Requirement Coverage

The initial execution backlog provides explicit non-planning coverage for every accepted requirement:

| Requirement | Primary execution coverage |
| --- | --- |
| FR-001 five-borough continuous road network | T012, T014 |
| FR-002 real geographic road derivation | T003, T004, T006, T010, T012 |
| FR-003 widths/lanes/direction/intersections | T003, T004, T006, T010, T012 |
| FR-004 elevation and grade separation | T010, T012 |
| FR-005 runtime tile streaming | T004, T005, T006, T012, T014 |
| FR-006 GC8-era initial vehicle / distributable equivalent | T007, T013 |
| FR-007 physics-driven vehicle | T007, T008, T014 |
| FR-008 controllable drift and handbrake | T008, T014 |
| FR-009 isometric follow camera | T009, T014 |
| FR-010 simplified/procedural scenery | T011, T014 |
| FR-011 free-driving mode | T008, T009, T014 |
| FR-012 reset/recovery | T009, T014 |
| FR-013 desktop driving controls | T002, T009, T014 |
| QR-001 modern desktop browser / Three.js | T002, T014 |
| QR-002 meter-based 1:1 coordinates | T003, T004, T005, T010, T012 |
| QR-003 bounded streaming memory/physics | T005, T011, T014 |
| QR-004 compiler/runtime separation | T003, T004, T010, T012 |
| QR-005 license/attribution compliance | T002, T003, T011, T013, T014 |

### Sequencing

- **Foundation can proceed in parallel:** T002 (web scaffold) and T003 (GIS/compiler foundation).
- **First playable slice:** T004 -> T005 -> T006 -> T007, with T009 joining once the car exists.
- **Driving quality:** T008 tunes the vehicle on real compiled roads instead of a synthetic test track only.
- **Map hard cases before scale:** T010 solves elevation/grade separation before T012 expands to the complete city.
- **Scenery can proceed alongside road expansion:** T011 depends on the source/compiler and streamer boundaries but must not block physics work.
- **Legal/asset gate can proceed independently:** T013 can replace prototype art without coupling to physics.
- **Release-style validation:** T014 depends on the integrated city, vehicle, camera/input, scenery, and licensing work.

Execution should optimize for reaching a convincing Manhattan vertical slice quickly, then harden the compiler and expand to five boroughs. A citywide map should not be generated merely to discover that the car, camera, or streaming architecture needs to be redesigned.
