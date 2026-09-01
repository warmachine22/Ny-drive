from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .adapters.nyc_buildings import normalize_building_geojson
from .adapters.nyc_cscl import normalize_cscl_geojson
from .adapters.nyc_roadbed import normalize_roadbed_geojson
from .crs import PROJECT_CRS, PROJECT_ORIGIN_WGS84
from .model import BuildingFootprint, RoadCenterline, RoadSurface
from .tiling import TILE_SIZE_M, compile_tiles, validate_tile_local_coordinates
from .vertical import ElevationSampler, VerticalResolver


def normalize_snapshot(
    snapshot: Mapping[str, Any],
) -> tuple[list[RoadSurface], list[RoadCenterline]]:
    sources = snapshot.get("sources") or {}
    roadbed_meta = sources.get("roadbed") or {}
    centerline_meta = sources.get("centerline") or {}
    roadbed = normalize_roadbed_geojson(
        snapshot["roadbed"],
        source_revision=roadbed_meta.get("data_revision"),
    )
    roads = normalize_cscl_geojson(
        snapshot["centerline"],
        source_revision=centerline_meta.get("data_revision"),
    )
    return roadbed, roads


def normalize_buildings(snapshot: Mapping[str, Any]) -> list[BuildingFootprint]:
    collection = snapshot.get("buildings")
    if not isinstance(collection, Mapping):
        return []
    sources = snapshot.get("sources") or {}
    building_meta = sources.get("buildings") or {}
    return normalize_building_geojson(
        collection,
        source_revision=building_meta.get("data_revision"),
    )


def compile_normalized_snapshot(
    snapshot: Mapping[str, Any],
    roadbed: Sequence[RoadSurface],
    roads: Sequence[RoadCenterline],
    *,
    buildings: Sequence[BuildingFootprint] = (),
    elevation_sampler: ElevationSampler | None = None,
    return_vertical: bool = False,
):
    if not buildings and isinstance(snapshot.get("buildings"), Mapping):
        buildings = normalize_buildings(snapshot)
    vertical = (
        VerticalResolver(roadbed, roads, elevation_sampler)
        if elevation_sampler is not None
        else None
    )
    tiles = compile_tiles(roadbed, roads, buildings, vertical=vertical)
    validate_tile_local_coordinates(tiles)

    tile_entries = []
    for key, tile in tiles.items():
        ix, iy = tile["index"]
        tile_entries.append(
            {
                "tile_id": key,
                "index": [ix, iy],
                "origin_m": tile["origin_m"],
                "file": f"tiles/{ix}_{iy}.json",
                "road_surface_count": len(tile["road_surfaces"]),
                "road_count": len(tile["roads"]),
                "building_count": len(tile.get("buildings", [])),
            }
        )

    sources = snapshot.get("sources") or {}
    manifest = {
        "schema_version": 2 if vertical is not None else 1,
        "name": snapshot.get("name", "unnamed-fixture"),
        "coordinate_system": {
            "crs": PROJECT_CRS.to_string(),
            "units": "metres",
            "project_origin_wgs84": list(PROJECT_ORIGIN_WGS84),
            "tile_size_m": TILE_SIZE_M,
        },
        "bounds_wgs84": snapshot.get("bounds_wgs84"),
        "sources": sources,
        "input_counts": {
            "roadbed": len(roadbed),
            "centerline": len(roads),
            "buildings": len(buildings),
        },
        "tile_count": len(tiles),
        "tiles": tile_entries,
    }
    if buildings:
        source_height_count = sum(building.height_source == "nyc-height-roof" for building in buildings)
        manifest["scenery"] = {
            "source_key": "nyc-building-footprints",
            "building_count": len(buildings),
            "source_height_count": source_height_count,
            "fallback_height_count": len(buildings) - source_height_count,
            "collision_policy": "visual-only",
        }
    if vertical is not None:
        manifest["elevation"] = {
            "source_key": vertical.source_key,
            "units": "metres",
            "vertical_datum": "NAVD88",
        }
        manifest["vertical_diagnostics"] = vertical.diagnostics_payload()
    if return_vertical:
        return manifest, tiles, vertical
    return manifest, tiles


def compile_snapshot(
    snapshot: Mapping[str, Any],
    *,
    elevation_sampler: ElevationSampler | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    roadbed, roads = normalize_snapshot(snapshot)
    buildings = normalize_buildings(snapshot)
    manifest, tiles = compile_normalized_snapshot(
        snapshot,
        roadbed,
        roads,
        buildings=buildings,
        elevation_sampler=elevation_sampler,
    )
    return manifest, tiles


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_compiled_fixture(
    snapshot_path: Path,
    output_dir: Path,
    *,
    elevation_sampler: ElevationSampler | None = None,
) -> dict[str, Any]:
    manifest, tiles = compile_snapshot(
        load_snapshot(snapshot_path),
        elevation_sampler=elevation_sampler,
    )
    tiles_dir = output_dir / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)

    for stale in tiles_dir.glob("*.json"):
        stale.unlink()
    for entry in manifest["tiles"]:
        payload = tiles[entry["tile_id"]]
        target = output_dir / entry["file"]
        target.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
