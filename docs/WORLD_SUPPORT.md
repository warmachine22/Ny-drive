# Prototype non-road support

T017 adds a temporary, streamed non-road support layer for the current flat Manhattan development fixture. Its purpose is to make ordinary road departures recoverable while true terrain/elevation work is still pending.

## Authority

NYC Roadbed polygons remain the authoritative driving surface and stay at runtime elevation `y = 0` for the current flat fixture. Support ground is deliberately lower (`-0.25 m`) and has lower friction, so suspension rays encounter Roadbed first wherever Roadbed exists.

The support layer must never be interpreted as geographic terrain accuracy.

## Streaming lifecycle

- eligible support visuals are attached with rendered world tiles;
- support colliders exist only while the corresponding tile is physics-active;
- support visuals/colliders rebase by the same floating-origin shift as Roadbed geometry;
- support is detached/disposed with the tile, so memory/collider count remains bounded by streaming radii.

## Grade-separation guard

The flat support policy refuses to create a slab for a tile containing a road marked as `bridge`, `tunnel`, or a non-zero `layer`. This is intentionally conservative: flattening a vertically structured tile could create a false intersection under an overpass or through a tunnel.

T010 owns real elevation/grade-separated road structures and may replace this eligibility rule with source-derived terrain/elevation geometry. Do not weaken the guard merely to make a complex tile visually filled.

## Fall recovery

A `FallRecoveryMonitor` watches vehicle local height. Falling below the configured safety threshold (currently `-5 m`) or receiving a non-finite height triggers the existing asynchronous safe-road recovery flow once. Recovery continues to use the nearest loaded Roadbed/centerline pose and heading rather than a second teleport system.

The monitor is latched during a fall so one bad frame cannot schedule repeated resets. It clears after a valid-height recovery or explicit reset completion.
