# Procedural NYC scenery

Ny-drive scenery is intentionally simple city massing, not a photorealistic reconstruction. Road geometry and driving topology remain the product priority; scenery exists to make the real street network legible while keeping a browser-sized active world.

## Authoritative geometry

Building footprint geometry comes from NYC Office of Technology and Innovation Building Footprints (`5zhs-2jue`). `DOITT_ID` is the stable building identity. The compiler omits feature code `1003` placeholder triangles because they do not represent surveyed building perimeters.

Positive `HEIGHT_ROOF` values are interpreted as roof height above building ground, converted from feet to metres, and serialized with `height_source = "nyc-height-roof"`. The source `GROUND_ELEVATION` is retained in metres as provenance, but it is not blindly used as runtime base Y because the active road world may be a flat schema-v1 fixture or may use the separately pinned NAVD88 DEM.

## Missing-height fallback

A missing or zero roof height never becomes a fake measured value. It is serialized as `height_source = "deterministic-visual-fallback"` using these fixed visual rules:

- parking, canopy, tank, auxiliary/temporary structure, skybridge, and garage feature codes: 4.5 m;
- other footprints under 150 m²: 7.5 m;
- other footprints from 150 m² to under 1,000 m²: 12 m;
- other footprints at least 1,000 m²: 18 m.

These values are style/massing defaults only. They are deliberately easy to identify and replace if a later source provides a measured height.

## Vertical placement

For schema-v2 builds, a building's visual base samples the same pinned terrain elevation source used by the road compiler. For the schema-v1 Flatiron development fixture the base is 0 m, matching its flat road world. If a schema-v2 terrain sample is missing, scenery falls back to 0 m and labels that base as `missing-terrain-fallback` rather than using a differently-derived absolute elevation silently.

## Runtime performance contract

Each streamed 256 m tile merges all of its building polygons into one Three.js buffer geometry and renders that geometry with one shared simple material. Draw-call growth is therefore bounded by rendered tiles, not by building count. Tile detach disposes the merged geometry with the rest of that tile's visual resources.

Buildings are visual-only in this task. Rapier activation continues to create only driving/support colliders; there is no rigid body or collider per decorative building. If later gameplay requires wall collision, it should be introduced as a deliberately selected coarse collision layer rather than mirroring every visual footprint into physics.

## Attribution

Source-data provenance is pinned in `tools/map_compiler/sources.lock.json`. Geographic-source notices live in `THIRD_PARTY_NOTICES.md`. No external procedural art package or building-model asset is used for this massing system; geometry is generated at runtime from the source footprints using the project's existing Three.js dependency.
