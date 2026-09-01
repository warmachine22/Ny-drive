from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable

from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .model import BuildingFootprint, RoadCenterline, RoadSurface
from .vertical import VerticalResolver

TILE_SIZE_M = 256.0
ROUND_DIGITS = 3
ELEVATION_ROUND_DIGITS = 3
VERTICAL_SAMPLE_SPACING_M = 16.0
EPSILON = 1e-7


def tile_id(ix: int, iy: int) -> str:
    return f"{ix}:{iy}"


def tile_origin(ix: int, iy: int) -> tuple[float, float]:
    return ix * TILE_SIZE_M, iy * TILE_SIZE_M


def tile_bounds(ix: int, iy: int) -> tuple[float, float, float, float]:
    ox, oy = tile_origin(ix, iy)
    return ox, oy, ox + TILE_SIZE_M, oy + TILE_SIZE_M


def _candidate_tiles(bounds: tuple[float, float, float, float]) -> Iterable[tuple[int, int]]:
    min_x, min_y, max_x, max_y = bounds
    max_x_inside = math.nextafter(max_x, -math.inf)
    max_y_inside = math.nextafter(max_y, -math.inf)
    for ix in range(math.floor(min_x / TILE_SIZE_M), math.floor(max_x_inside / TILE_SIZE_M) + 1):
        for iy in range(math.floor(min_y / TILE_SIZE_M), math.floor(max_y_inside / TILE_SIZE_M) + 1):
            yield ix, iy


def _polygon_geometry(polygons) -> BaseGeometry:
    parts = [
        Polygon(
            [(point.x, point.y) for point in polygon.outer],
            [[(point.x, point.y) for point in hole] for hole in polygon.holes],
        )
        for polygon in polygons
    ]
    return unary_union(parts)


def _surface_geometry(surface: RoadSurface) -> BaseGeometry:
    return _polygon_geometry(surface.polygons)


def _building_geometry(building: BuildingFootprint) -> BaseGeometry:
    return _polygon_geometry(building.polygons)


def _road_geometry(road: RoadCenterline) -> BaseGeometry:
    lines = [LineString([(point.x, point.y) for point in path]) for path in road.paths if len(path) >= 2]
    if not lines:
        return GeometryCollection()
    return lines[0] if len(lines) == 1 else MultiLineString(lines)


def _polygon_parts(geometry: BaseGeometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry] if geometry.area > EPSILON else []
    if isinstance(geometry, MultiPolygon):
        return [part for part in geometry.geoms if part.area > EPSILON]
    if isinstance(geometry, GeometryCollection):
        return [part for child in geometry.geoms for part in _polygon_parts(child)]
    return []


def _line_parts(geometry: BaseGeometry) -> list[LineString]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, LineString):
        return [geometry] if geometry.length > EPSILON else []
    if isinstance(geometry, MultiLineString):
        return [part for part in geometry.geoms if part.length > EPSILON]
    if isinstance(geometry, GeometryCollection):
        return [part for child in geometry.geoms for part in _line_parts(child)]
    return []


def _densify_coords(coords, max_spacing_m: float = VERTICAL_SAMPLE_SPACING_M):
    points = [(float(x), float(y)) for x, y, *_ in coords]
    if len(points) < 2:
        return points
    result: list[tuple[float, float]] = []
    for first, second in zip(points, points[1:]):
        dx = second[0] - first[0]
        dy = second[1] - first[1]
        length = math.hypot(dx, dy)
        steps = max(1, math.ceil(length / max_spacing_m))
        for step in range(steps):
            t = step / steps
            result.append((first[0] + dx * t, first[1] + dy * t))
    result.append(points[-1])
    return result


def _local_point(
    x: float,
    y: float,
    origin: tuple[float, float],
    elevation_m: float | None = None,
) -> list[float]:
    point = [round(x - origin[0], ROUND_DIGITS), round(y - origin[1], ROUND_DIGITS)]
    if elevation_m is not None:
        point.append(round(elevation_m, ELEVATION_ROUND_DIGITS))
    return point


def _serialize_polygon(
    polygon: Polygon,
    origin: tuple[float, float],
    *,
    surface: RoadSurface | None = None,
    vertical: VerticalResolver | None = None,
) -> dict[str, Any]:
    def ring_points(coords):
        source_coords = _densify_coords(coords) if vertical is not None and surface is not None else list(coords)
        result = []
        for x, y, *_ in source_coords:
            elevation = (
                vertical.surface_elevation(surface, x, y)
                if vertical is not None and surface is not None
                else None
            )
            result.append(_local_point(x, y, origin, elevation))
        return result

    return {
        "outer": ring_points(polygon.exterior.coords),
        "holes": [ring_points(ring.coords) for ring in polygon.interiors],
    }


def _serialize_line(
    line: LineString,
    origin: tuple[float, float],
    *,
    road: RoadCenterline | None = None,
    vertical: VerticalResolver | None = None,
) -> list[list[float]]:
    coords = _densify_coords(line.coords) if vertical is not None else list(line.coords)
    return [
        _local_point(
            x,
            y,
            origin,
            vertical.road_elevation(road, x, y) if vertical is not None and road is not None else None,
        )
        for x, y, *_ in coords
    ]


def _empty_tile(ix: int, iy: int, schema_version: int) -> dict[str, Any]:
    origin = tile_origin(ix, iy)
    return {
        "schema_version": schema_version,
        "tile_id": tile_id(ix, iy),
        "index": [ix, iy],
        "origin_m": [origin[0], origin[1]],
        "size_m": TILE_SIZE_M,
        "road_surfaces": [],
        "roads": [],
        "buildings": [],
    }


def _building_base_elevation(building_geometry: BaseGeometry, vertical: VerticalResolver | None) -> tuple[float, str]:
    if vertical is None or building_geometry.is_empty:
        return 0.0, "flat-fixture"
    point = building_geometry.representative_point()
    sampled = vertical.elevation.sample(float(point.x), float(point.y))
    if sampled is None:
        return 0.0, "missing-terrain-fallback"
    return float(sampled), vertical.source_key


def compile_tiles(
    surfaces: Iterable[RoadSurface],
    roads: Iterable[RoadCenterline],
    buildings: Iterable[BuildingFootprint] = (),
    *,
    vertical: VerticalResolver | None = None,
) -> dict[str, dict[str, Any]]:
    surfaces = list(surfaces)
    roads = list(roads)
    buildings = list(buildings)
    schema_version = 2 if vertical is not None else 1
    tiles: dict[tuple[int, int], dict[str, Any]] = {}

    for surface in surfaces:
        geometry = _surface_geometry(surface)
        if geometry.is_empty:
            continue
        stable_id = f"{surface.provenance.source_key}:{surface.source_id}"
        association = vertical.surface_association(surface) if vertical is not None else None
        for ix, iy in _candidate_tiles(geometry.bounds):
            clipped = geometry.intersection(box(*tile_bounds(ix, iy)))
            parts = _polygon_parts(clipped)
            if not parts:
                continue
            target = tiles.setdefault((ix, iy), _empty_tile(ix, iy, schema_version))
            origin = tile_origin(ix, iy)
            item = {
                "stable_id": stable_id,
                "source_id": surface.source_id,
                "source_key": surface.provenance.source_key,
                "feature_code": surface.feature_code,
                "sub_code": surface.sub_code,
                "status": surface.status,
                "polygons": [
                    _serialize_polygon(part, origin, surface=surface, vertical=vertical)
                    for part in parts
                ],
            }
            if vertical is not None and association is not None:
                item["vertical_status"] = association.status
                item["associated_road_id"] = (
                    association.road_profile.stable_id if association.road_profile is not None else None
                )
                item["elevation_source"] = vertical.source_key
            target["road_surfaces"].append(item)

    for building in buildings:
        geometry = _building_geometry(building)
        if geometry.is_empty:
            continue
        stable_id = f"{building.provenance.source_key}:{building.source_id}"
        base_elevation_m, base_elevation_source = _building_base_elevation(geometry, vertical)
        for ix, iy in _candidate_tiles(geometry.bounds):
            clipped = geometry.intersection(box(*tile_bounds(ix, iy)))
            parts = _polygon_parts(clipped)
            if not parts:
                continue
            target = tiles.setdefault((ix, iy), _empty_tile(ix, iy, schema_version))
            origin = tile_origin(ix, iy)
            target["buildings"].append(
                {
                    "stable_id": stable_id,
                    "source_id": building.source_id,
                    "source_key": building.provenance.source_key,
                    "feature_code": building.feature_code,
                    "bin": building.bin,
                    "name": building.name,
                    "construction_year": building.construction_year,
                    "height_m": round(building.height_m, ELEVATION_ROUND_DIGITS),
                    "height_source": building.height_source,
                    "base_elevation_m": round(base_elevation_m, ELEVATION_ROUND_DIGITS),
                    "base_elevation_source": base_elevation_source,
                    "source_ground_elevation_m": (
                        round(building.source_ground_elevation_m, ELEVATION_ROUND_DIGITS)
                        if building.source_ground_elevation_m is not None
                        else None
                    ),
                    "polygons": [_serialize_polygon(part, origin) for part in parts],
                }
            )

    for road in roads:
        geometry = _road_geometry(road)
        if geometry.is_empty:
            continue
        stable_id = f"{road.provenance.source_key}:{road.source_id}"
        for ix, iy in _candidate_tiles(geometry.bounds):
            clipped = geometry.intersection(box(*tile_bounds(ix, iy)))
            parts = _line_parts(clipped)
            if not parts:
                continue
            target = tiles.setdefault((ix, iy), _empty_tile(ix, iy, schema_version))
            origin = tile_origin(ix, iy)
            item = {
                "stable_id": stable_id,
                "source_id": road.source_id,
                "source_key": road.provenance.source_key,
                "name": road.name,
                "directionality": road.semantics.directionality.value,
                "lanes": road.semantics.lanes,
                "lanes_forward": road.semantics.lanes_forward,
                "lanes_backward": road.semantics.lanes_backward,
                "width_m": road.semantics.width_m,
                "road_class": road.semantics.road_class,
                "bridge": road.semantics.bridge,
                "tunnel": road.semantics.tunnel,
                "layer": road.semantics.layer,
                "from_level_code": road.source_properties.get("from_level_code")
                or road.source_properties.get("from_level"),
                "to_level_code": road.source_properties.get("to_level_code")
                or road.source_properties.get("to_level_c"),
                "paths": [
                    _serialize_line(part, origin, road=road, vertical=vertical)
                    for part in parts
                ],
            }
            if vertical is not None:
                profile = vertical.road_profile(road)
                item["ramp"] = profile.structure_kind == "ramp"
                item["vertical_structure"] = profile.structure_kind
                item["vertical_level_source"] = profile.level_source
                item["from_level"] = profile.from_level
                item["to_level"] = profile.to_level
                item["elevation_source"] = vertical.source_key
            target["roads"].append(item)

    diagnostics = vertical.diagnostics_payload() if vertical is not None else []
    result: dict[str, dict[str, Any]] = {}
    for (ix, iy), payload in sorted(tiles.items()):
        payload["road_surfaces"].sort(key=lambda item: item["stable_id"])
        payload["roads"].sort(key=lambda item: item["stable_id"])
        payload["buildings"].sort(key=lambda item: item["stable_id"])
        if vertical is not None:
            feature_ids = {
                item["stable_id"]
                for collection in (payload["road_surfaces"], payload["roads"])
                for item in collection
            }
            payload["vertical_diagnostics"] = [
                diagnostic
                for diagnostic in diagnostics
                if diagnostic["feature_id"] in feature_ids
            ]
        result[tile_id(ix, iy)] = payload
    return result


def validate_tile_local_coordinates(tiles: dict[str, dict[str, Any]]) -> None:
    tolerance = 0.002
    for payload in tiles.values():
        for collection in ("road_surfaces", "buildings"):
            for feature in payload.get(collection, []):
                rings = []
                for polygon in feature["polygons"]:
                    rings.append(polygon["outer"])
                    rings.extend(polygon["holes"])
                for ring in rings:
                    for point in ring:
                        x, y = point[:2]
                        if not (
                            -tolerance <= x <= TILE_SIZE_M + tolerance
                            and -tolerance <= y <= TILE_SIZE_M + tolerance
                        ):
                            raise ValueError(
                                f"{collection} coordinate escaped tile {payload['tile_id']}: {(x, y)}"
                            )
        for road in payload["roads"]:
            for path in road["paths"]:
                for point in path:
                    x, y = point[:2]
                    if not (
                        -tolerance <= x <= TILE_SIZE_M + tolerance
                        and -tolerance <= y <= TILE_SIZE_M + tolerance
                    ):
                        raise ValueError(
                            f"road coordinate escaped tile {payload['tile_id']}: {(x, y)}"
                        )


def feature_tile_counts(tiles: dict[str, dict[str, Any]], collection: str) -> Counter[str]:
    return Counter(item["stable_id"] for tile in tiles.values() for item in tile[collection])
