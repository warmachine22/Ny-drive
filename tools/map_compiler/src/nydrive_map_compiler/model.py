from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping

Scalar = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Polygon2D:
    outer: tuple[Point2D, ...]
    holes: tuple[tuple[Point2D, ...], ...] = ()


class Directionality(StrEnum):
    BOTH = "both"
    FORWARD = "forward"
    REVERSE = "reverse"


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    source_key: str
    feature_id: str
    source_crs: str
    source_revision: str | None = None


@dataclass(frozen=True, slots=True)
class RoadSemantics:
    directionality: Directionality = Directionality.BOTH
    lanes: int | None = None
    lanes_forward: int | None = None
    lanes_backward: int | None = None
    width_m: float | None = None
    road_class: str | None = None
    bridge: bool = False
    tunnel: bool = False
    layer: int = 0
    tags: Mapping[str, Scalar] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RoadCenterline:
    source_id: str
    paths: tuple[tuple[Point2D, ...], ...]
    name: str | None
    borough: str | None
    feature_type: str | None
    route_type: str | None
    roadway_type: str | None
    build_status: str | None
    semantics: RoadSemantics
    provenance: SourceProvenance
    source_properties: Mapping[str, Scalar] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RoadSurface:
    source_id: str
    polygons: tuple[Polygon2D, ...]
    feature_code: int | None
    sub_code: int | None
    status: str | None
    provenance: SourceProvenance
    source_properties: Mapping[str, Scalar] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BuildingFootprint:
    source_id: str
    polygons: tuple[Polygon2D, ...]
    height_m: float
    height_source: str
    source_ground_elevation_m: float | None
    feature_code: int | None
    bin: str | None
    name: str | None
    construction_year: int | None
    provenance: SourceProvenance
    source_properties: Mapping[str, Scalar] = field(default_factory=dict)
