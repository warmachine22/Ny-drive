# Durable Decisions

Keep only short decisions another worker needs in order to continue consistently and that cannot be recovered cheaply from `PRODUCT.md`, `PLAN.md`, code, tests, or Git history.

Format:

- `D001 [YYYY-MM-DD] Decision — short reason.`

Use one or two lines per item. Skip routine implementation choices.

- `D001 [2026-08-30] World/compiler CRS is EPSG:32118 (NAD83 / New York Long Island, meters); NYC CSCL source coordinates in EPSG:2263 are converted explicitly. This supersedes the provisional EPSG:32618 note in the original plan.`
- `D002 [2026-08-30] NYC Roadbed polygons define the authoritative driveable/render/collision footprint; centerlines carry names, direction, lane, width, class, and level metadata but must not become fixed-width collision ribbons.`
- `D003 [2026-08-30] Physics-active world tiles own one static Rapier roadbed trimesh each with FIX_INTERNAL_EDGES; activate/deactivate/rebase is idempotent and bounded by the streamer. World-level Rapier scene-query acceleration is assumed current only after the normal physics/query update path runs.`
- `D004 [2026-08-30] The player tile must be physics-ready before dynamic vehicle substeps. T007 owns real vehicle traversal across tile seams because T006 necessarily precedes the dynamic vehicle in the dependency graph.`
- `D005 [2026-08-30] Drift/handbrake tuning (T008) follows player camera/reset integration (T009) so subjective handling is judged through the actual near-isometric driving experience rather than the placeholder camera.`
- `D006 [2026-08-30] Rapier is currently imported statically by road collision and vehicle modules, so the PhysicsWorld dynamic import does not split it from the production bundle. Do not derail vehicle/world correctness to optimize this early; T014 must measure startup payload and decide whether Rapier/code splitting is warranted.`
- `D007 [2026-08-31] Ground elevation uses the 2017 NYC LiDAR hydro-flattened bare-earth DEM, while official NYC endpoint level codes and structure types take precedence for grade-separated roads and OSM supplements missing semantics. A maximum 5 m continuous mid-span envelope is the diagnostic/replaceable fallback when bridge/tunnel interiors need separation but stronger vertical data is absent; it is not surveyed clearance.`
