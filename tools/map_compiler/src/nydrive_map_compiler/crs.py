from __future__ import annotations

from functools import lru_cache
from typing import Iterable

from pyproj import CRS, Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

# NYC's official DCM source data is published in EPSG:2263 (US survey feet).
# The game compiler normalizes everything into the metric sibling State Plane CRS.
PROJECT_CRS = CRS.from_epsg(32118)  # NAD83 / New York Long Island (metres)
WGS84 = CRS.from_epsg(4326)
PROJECT_ORIGIN_WGS84 = (-74.0060, 40.7128)


@lru_cache(maxsize=16)
def transformer(source_crs: str | int | CRS, target_crs: str | int | CRS = PROJECT_CRS) -> Transformer:
    return Transformer.from_crs(CRS.from_user_input(source_crs), CRS.from_user_input(target_crs), always_xy=True)


def project_origin_xy() -> tuple[float, float]:
    return transformer(WGS84).transform(*PROJECT_ORIGIN_WGS84)


def to_project_xy(x: float, y: float, source_crs: str | int | CRS) -> tuple[float, float]:
    px, py = transformer(source_crs).transform(x, y)
    ox, oy = project_origin_xy()
    return px - ox, py - oy


def transform_geometry(geometry: BaseGeometry, source_crs: str | int | CRS) -> BaseGeometry:
    convert = transformer(source_crs)
    ox, oy = project_origin_xy()

    def _convert(xs: Iterable[float], ys: Iterable[float], zs: Iterable[float] | None = None):
        tx, ty = convert.transform(xs, ys)
        local_x = [x - ox for x in tx]
        local_y = [y - oy for y in ty]
        if zs is None:
            return local_x, local_y
        return local_x, local_y, list(zs)

    return shapely_transform(_convert, geometry)
