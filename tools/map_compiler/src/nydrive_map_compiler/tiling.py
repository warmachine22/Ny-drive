from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .model import Point2D, Polygon2D, RoadCenterline, RoadSurface

TILE_SIZE_M = 256.0
ROUND_DIGITS = 3
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


def _surface_geometry(surface: RoadSurface) -> BaseGeometry:
    polygons = [
        Polygon(
            [(point.x, point.y) for point in polygon.outer],
            [[(point.x, point.y) for point in hole] for hole in polygon.holes],
        )
        for polygon in surface.polygons
    ]
    return unary_union(polygons)


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


def _local_point(x: float, y: float, origin: tuple[float, float]) -> list[float]:
    return [round(x - origin[0], ROUND_DIGITS), round(y - origin[1], ROUND_DIGITS)]


def _serialize_polygon(polygon: Polygon, origin: tuple[float, float]) -> dict[str, Any]:
    return {
        "outer": [_local_point(x, y, origin) for x, y, *_ in polygon.exterior.coords],
        "holes": [
            [_local_point(x, y, origin) for x, y, *_ in ring.coords]
            for ring in polygon.interiors
        ],
    }


def _serialize_line(line: LineString, origin: tuple[float, float]) -> list[list[float]]:
    return [_local_point(x, y, origin) for x, y, *_ in line.coords]


def _empty_tile(ix: int, iy: int) -> dict[str, Any]:
    origin = tile_origin(ix, iy)
    return {
        "schema_version": 1,
        "tile_id": tile_id(ix, iy),
        "index": [ix, iy],
        "origin_m": [origin[0], origin[1]],
        "size_m": TILE_SIZE_M,
        "road_surfaces": [],
        "roads": [],
    }


def compile_tiles(
    surfaces: Iterable[RoadSurface],
    roads: Iterable[RoadCenterline],
) -> dict[str, dict[str, Any]]:
    tiles: dict[tuple[int, int], dict[str, Any]] = {}

    for surface in surfaces:
        geometry = _surface_geometry(surface)
        if geometry.is_empty:
            continue
        stable_id = f"{surface.provenance.source_key}:{surface.source_id}"
        for ix, iy in _candidate_tiles(geometry.bounds):
            clipped = geometry.intersection(box(*tile_bounds(ix, iy)))
            parts = _polygon_parts(clipped)
            if not parts:
                continue
            target = tiles.setdefault((ix, iy), _empty_tile(ix, iy))
            origin = tile_origin(ix, iy)
            target["road_surfaces"].append(
                {
                    "stable_id": stable_id,
                    "source_id": surface.source_id,
                    "source_key": surface.provenance.source_key,
                    "feature_code": surface.feature_code,
                    "sub_code": surface.sub_code,
                    "status": surface.status,
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
            target = tiles.setdefault((ix, iy), _empty_tile(ix, iy))
            origin = tile_origin(ix, iy)
            target["roads"].append(
                {
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
                    "from_level_code": road.source_properties.get("from_level_code") or road.source_properties.get("from_level"),
                    "to_level_code": road.source_properties.get("to_level_code") or road.source_properties.get("to_level_c"),
                    "paths": [_serialize_line(part, origin) for part in parts],
                }
            )

    result: dict[str, dict[str, Any]] = {}
    for (ix, iy), payload in sorted(tiles.items()):
        payload["road_surfaces"].sort(key=lambda item: item["stable_id"])
        payload["roads"].sort(key=lambda item: item["stable_id"])
        result[tile_id(ix, iy)] = payload
    return result


def validate_tile_local_coordinates(tiles: dict[str, dict[str, Any]]) -> None:
    tolerance = 0.002
    for payload in tiles.values():
        for surface in payload["road_surfaces"]:
            rings = []
            for polygon in surface["polygons"]:
                rings.append(polygon["outer"])
                rings.extend(polygon["holes"])
            for ring in rings:
                for x, y in ring:
                    if not (-tolerance <= x <= TILE_SIZE_M + tolerance and -tolerance <= y <= TILE_SIZE_M + tolerance):
                        raise ValueError(f"surface coordinate escaped tile {payload['tile_id']}: {(x, y)}")
        for road in payload["roads"]:
            for path in road["paths"]:
                for x, y in path:
                    if not (-tolerance <= x <= TILE_SIZE_M + tolerance and -tolerance <= y <= TILE_SIZE_M + tolerance):
                        raise ValueError(f"road coordinate escaped tile {payload['tile_id']}: {(x, y)}")


def feature_tile_counts(tiles: dict[str, dict[str, Any]], collection: str) -> Counter[str]:
    return Counter(item["stable_id"] for tile in tiles.values() for item in tile[collection])
