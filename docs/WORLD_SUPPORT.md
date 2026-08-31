# Prototype non-road support

T017 adds a temporary, streamed non-road support layer for the current flat Manhattan development fixture. Its purpose is to make ordinary road departures recoverable while true terrain/elevation work is still pending.

## Authority

NYC Roadbed polygons remain the authoritative driving surface and stay at runtime elevation `y = 0` for the current schema-v1 flat fixture. Support ground is deliberately lower (`-0.25 m`) and has lower friction, so suspension rays encounter Roadbed first wherever Roadbed exists.

The support layer must never be interpreted as geographic terrain accuracy.

## Streaming lifecycle

- eligible support visuals are attached with rendered world tiles;
- support colliders exist only while the corresponding tile is physics-active;
- support visuals/colliders rebase by the same floating-origin shift as Roadbed geometry;
- support is detached/disposed with the tile, so memory/collider count remains bounded by streaming radii.

## Grade-separation guard

For legacy schema-v1 flat tiles, the support policy refuses to create a slab for a tile containing a road marked as `bridge`, `tunnel`, or a non-zero `layer`. This is intentionally conservative: flattening a vertically structured tile could create a false intersection under an overpass or through a tunnel.

T010 adds source-derived elevation/grade-separated road structures as tile schema v2. **All schema-v2 tiles categorically disable the T017 flat support slab**, even when a particular tile contains only at-grade roads. A flat plane under a real-elevation tile could cut through below-grade roads, occupy space below bridge decks, or contradict terrain grade.

Future source-derived terrain may replace the prototype support behavior for elevation-enabled worlds, but it must be compiled and streamed as real geometry rather than weakening this guard.

See `docs/ELEVATION_AND_GRADE_SEPARATION.md` for the schema-v2 vertical topology contract.

## Fall recovery

A `FallRecoveryMonitor` watches vehicle height relative to the nearest plausible road elevation. Falling more than the configured safety drop (currently `5 m`) below that reference, or receiving a non-finite height, triggers the existing asynchronous safe-road recovery flow once. This preserves recovery for genuine falls while allowing legitimate below-grade tunnel elevations.

Recovery continues to use the nearest loaded Roadbed/centerline pose and heading rather than a second teleport system. Elevation-aware poses allow stacked roads to be disambiguated using the vehicle's current height.

The monitor is latched during a fall so one bad frame cannot schedule repeated resets. It clears after a valid-height recovery or explicit reset completion.
