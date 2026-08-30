from __future__ import annotations

from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from .model import Point2D, Polygon2D


def _points(coords) -> tuple[Point2D, ...]:
    return tuple(Point2D(float(x), float(y)) for x, y, *_ in coords)


def line_paths(geometry: BaseGeometry) -> tuple[tuple[Point2D, ...], ...]:
    if isinstance(geometry, LineString):
        return (_points(geometry.coords),)
    if isinstance(geometry, MultiLineString):
        return tuple(_points(line.coords) for line in geometry.geoms)
    raise TypeError(f"Expected line geometry, got {geometry.geom_type}")


def _polygon(poly: Polygon) -> Polygon2D:
    return Polygon2D(
        outer=_points(poly.exterior.coords),
        holes=tuple(_points(ring.coords) for ring in poly.interiors),
    )


def surface_polygons(geometry: BaseGeometry) -> tuple[Polygon2D, ...]:
    if isinstance(geometry, Polygon):
        return (_polygon(geometry),)
    if isinstance(geometry, MultiPolygon):
        return tuple(_polygon(poly) for poly in geometry.geoms)
    raise TypeError(f"Expected polygon geometry, got {geometry.geom_type}")
