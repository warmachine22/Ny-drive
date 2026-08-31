from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Sequence

from pyproj import CRS
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from .crs import PROJECT_CRS, project_origin_xy, transformer
from .model import Point2D, RoadCenterline, RoadSurface

US_SURVEY_FOOT_TO_M = 1200.0 / 3937.0
DEFAULT_LEVEL_SEPARATION_M = 5.0
CSCL_AT_GRADE_LEVEL = 13
CSCL_NOT_APPLICABLE_LEVEL = 99
BRIDGE_SEGMENT_TYPE = "3"
TUNNEL_SEGMENT_TYPE = "4"
RAMP_SEGMENT_TYPE = "9"


class ElevationSampler(Protocol):
    source_key: str

    def sample(self, x: float, y: float) -> float | None:
        """Return local-project terrain elevation in metres."""


@dataclass(frozen=True, slots=True)
class VerticalDiagnostic:
    severity: str
    code: str
    feature_id: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "feature_id": self.feature_id,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class ProfileVertex:
    x: float
    y: float
    elevation_m: float


@dataclass(frozen=True, slots=True)
class RoadPathProfile:
    line: LineString
    vertices: tuple[ProfileVertex, ...]
    length_m: float

    def elevation_at(self, x: float, y: float) -> float:
        if len(self.vertices) == 1 or self.length_m <= 1e-9:
            return self.vertices[0].elevation_m
        distance = self.line.project(Point(x, y))
        coords = list(self.line.coords)
        walked = 0.0
        for index in range(len(coords) - 1):
            x0, y0 = coords[index]
            x1, y1 = coords[index + 1]
            segment = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
            if segment <= 1e-12:
                continue
            if distance <= walked + segment + 1e-9:
                t = max(0.0, min(1.0, (distance - walked) / segment))
                a = self.vertices[index].elevation_m
                b = self.vertices[index + 1].elevation_m
                return a + (b - a) * t
            walked += segment
        return self.vertices[-1].elevation_m


@dataclass(frozen=True, slots=True)
class RoadVerticalProfile:
    road: RoadCenterline
    paths: tuple[RoadPathProfile, ...]
    from_level: int
    to_level: int
    level_source: str
    structure_kind: str
    inferred_structure_clearance: bool

    @property
    def stable_id(self) -> str:
        return f"{self.road.provenance.source_key}:{self.road.source_id}"

    @property
    def is_structured(self) -> bool:
        return self.structure_kind != "at-grade" or self.from_level != 0 or self.to_level != 0

    def elevation_at(self, x: float, y: float) -> float:
        best: tuple[float, float] | None = None
        for path in self.paths:
            point = Point(x, y)
            distance = path.line.distance(point)
            elevation = path.elevation_at(x, y)
            if best is None or distance < best[0]:
                best = (distance, elevation)
        if best is None:
            raise ValueError(f"road {self.stable_id} has no usable vertical profile")
        return best[1]


@dataclass(frozen=True, slots=True)
class SurfaceVerticalAssociation:
    road_profile: RoadVerticalProfile | None
    status: str
    competing_road_ids: tuple[str, ...] = ()


class ConstantElevationSampler:
    def __init__(self, elevation_m: float = 0.0, source_key: str = "test-elevation") -> None:
        self.elevation_m = float(elevation_m)
        self.source_key = source_key

    def sample(self, x: float, y: float) -> float | None:
        del x, y
        return self.elevation_m


class RasterElevationSampler:
    """Read GeoTIFF DEM tiles into the project-local metric coordinate system."""

    def __init__(
        self,
        paths: Sequence[Path | str],
        *,
        source_key: str = "nyc-2017-lidar-bare-earth-dem",
        vertical_units: str = "us_survey_foot",
    ) -> None:
        if not paths:
            raise ValueError("at least one DEM path is required")
        try:
            import rasterio
        except ImportError as exc:  # pragma: no cover - dependency is pinned for production
            raise RuntimeError("RasterElevationSampler requires rasterio") from exc

        self.source_key = source_key
        self._datasets = [rasterio.open(Path(path)) for path in paths]
        self._vertical_scale = {
            "metre": 1.0,
            "meter": 1.0,
            "metres": 1.0,
            "meters": 1.0,
            "us_survey_foot": US_SURVEY_FOOT_TO_M,
            "ftus": US_SURVEY_FOOT_TO_M,
        }.get(vertical_units.lower())
        if self._vertical_scale is None:
            self.close()
            raise ValueError(f"unsupported DEM vertical units: {vertical_units}")
        self._origin_x, self._origin_y = project_origin_xy()
        self._transforms = []
        for dataset in self._datasets:
            if dataset.crs is None:
                self.close()
                raise ValueError(f"DEM has no CRS: {dataset.name}")
            self._transforms.append(transformer(PROJECT_CRS, CRS.from_user_input(dataset.crs)))

    def sample(self, x: float, y: float) -> float | None:
        absolute_x = x + self._origin_x
        absolute_y = y + self._origin_y
        for dataset, convert in zip(self._datasets, self._transforms, strict=True):
            sx, sy = convert.transform(absolute_x, absolute_y)
            if not (
                dataset.bounds.left <= sx <= dataset.bounds.right
                and dataset.bounds.bottom <= sy <= dataset.bounds.top
            ):
                continue
            value = float(next(dataset.sample([(sx, sy)]))[0])
            nodata = dataset.nodata
            if nodata is not None and abs(value - float(nodata)) <= 1e-9:
                continue
            if value != value:  # NaN
                continue
            return value * self._vertical_scale
        return None

    def close(self) -> None:
        for dataset in getattr(self, "_datasets", []):
            dataset.close()

    def __enter__(self) -> "RasterElevationSampler":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _source_property(road: RoadCenterline, *keys: str):
    lowered = {str(key).lower(): value for key, value in road.source_properties.items()}
    for key in keys:
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def cscl_level_offset(code: object) -> int | None:
    if code is None or str(code).strip() == "":
        return None
    try:
        value = int(str(code).strip())
    except ValueError:
        return None
    if value == CSCL_NOT_APPLICABLE_LEVEL:
        return None
    if 1 <= value <= 26:
        return value - CSCL_AT_GRADE_LEVEL
    return None


def road_level_endpoints(road: RoadCenterline) -> tuple[int, int, str]:
    from_code = cscl_level_offset(
        _source_property(road, "from_level_code", "from_level", "frm_lvl_co")
    )
    to_code = cscl_level_offset(_source_property(road, "to_level_code", "to_level_c", "to_lvl_co"))
    if from_code is not None or to_code is not None:
        if from_code is None:
            from_code = to_code
        if to_code is None:
            to_code = from_code
        assert from_code is not None and to_code is not None
        return from_code, to_code, "nyc-cscl-level-code"

    layer = int(road.semantics.layer)
    if layer != 0:
        return layer, layer, "osm-layer"

    return 0, 0, "terrain"


def road_structure_kind(road: RoadCenterline, from_level: int, to_level: int) -> str:
    feature_type = str(road.feature_type or "").strip()
    highway = str(road.semantics.tags.get("highway") or road.semantics.road_class or "")
    if feature_type == RAMP_SEGMENT_TYPE or highway.endswith("_link") or from_level != to_level:
        return "ramp"
    if road.semantics.bridge or feature_type == BRIDGE_SEGMENT_TYPE or min(from_level, to_level) > 0:
        return "bridge"
    if road.semantics.tunnel or feature_type == TUNNEL_SEGMENT_TYPE or max(from_level, to_level) < 0:
        return "tunnel"
    return "at-grade"


def _sample_or_diagnose(
    sampler: ElevationSampler,
    point: Point2D,
    diagnostics: list[VerticalDiagnostic],
    feature_id: str,
) -> float:
    value = sampler.sample(point.x, point.y)
    if value is None:
        diagnostics.append(
            VerticalDiagnostic(
                "error",
                "missing-elevation-sample",
                feature_id,
                f"DEM has no sample at ({point.x:.3f}, {point.y:.3f})",
            )
        )
        return 0.0
    return value


def _path_cumulative_distances(path: Sequence[Point2D]) -> tuple[list[float], float]:
    distances = [0.0]
    total = 0.0
    for first, second in zip(path, path[1:]):
        total += ((second.x - first.x) ** 2 + (second.y - first.y) ** 2) ** 0.5
        distances.append(total)
    return distances, total


def _build_path_profile(
    road: RoadCenterline,
    path: Sequence[Point2D],
    sampler: ElevationSampler,
    from_level: int,
    to_level: int,
    structure_kind: str,
    diagnostics: list[VerticalDiagnostic],
    *,
    clearance_envelope_m: float = 0.0,
) -> RoadPathProfile:
    stable_id = f"{road.provenance.source_key}:{road.source_id}"
    distances, length = _path_cumulative_distances(path)
    if structure_kind == "at-grade":
        elevations = [_sample_or_diagnose(sampler, point, diagnostics, stable_id) for point in path]
    else:
        start_terrain = _sample_or_diagnose(sampler, path[0], diagnostics, stable_id)
        end_terrain = _sample_or_diagnose(sampler, path[-1], diagnostics, stable_id)
        elevations = []
        for distance in distances:
            t = 0.0 if length <= 1e-9 else distance / length
            terrain_grade = start_terrain + (end_terrain - start_terrain) * t
            level = from_level + (to_level - from_level) * t
            envelope = 0.0
            if clearance_envelope_m > 0.0:
                envelope = math.sin(math.pi * t) * clearance_envelope_m
                if structure_kind == "tunnel":
                    envelope = -envelope
            elevations.append(
                terrain_grade + level * DEFAULT_LEVEL_SEPARATION_M + envelope
            )
    line = LineString([(point.x, point.y) for point in path])
    return RoadPathProfile(
        line=line,
        vertices=tuple(
            ProfileVertex(point.x, point.y, elevation)
            for point, elevation in zip(path, elevations, strict=True)
        ),
        length_m=length,
    )


class VerticalResolver:
    def __init__(
        self,
        surfaces: Iterable[RoadSurface],
        roads: Iterable[RoadCenterline],
        elevation: ElevationSampler,
    ) -> None:
        self.elevation = elevation
        self.diagnostics: list[VerticalDiagnostic] = []
        self._roads = list(roads)
        self._profiles: dict[int, RoadVerticalProfile] = {}
        self._surface_associations: dict[int, SurfaceVerticalAssociation] = {}

        road_geometries: list[LineString] = []
        indexed_profiles: list[RoadVerticalProfile] = []
        for road in self._roads:
            profile = self._build_road_profile(road)
            self._profiles[id(road)] = profile
            for path in profile.paths:
                road_geometries.append(path.line)
                indexed_profiles.append(profile)
        self._road_geometries = road_geometries
        self._indexed_profiles = indexed_profiles
        self._road_tree = STRtree(road_geometries) if road_geometries else None

        for surface in surfaces:
            self._surface_associations[id(surface)] = self._associate_surface(surface)

    @property
    def source_key(self) -> str:
        return self.elevation.source_key

    def _build_road_profile(self, road: RoadCenterline) -> RoadVerticalProfile:
        stable_id = f"{road.provenance.source_key}:{road.source_id}"
        from_level, to_level, level_source = road_level_endpoints(road)
        feature_type = str(road.feature_type or "").strip()
        bridge = road.semantics.bridge or feature_type == BRIDGE_SEGMENT_TYPE
        tunnel = road.semantics.tunnel or feature_type == TUNNEL_SEGMENT_TYPE
        if bridge and tunnel:
            self.diagnostics.append(
                VerticalDiagnostic(
                    "error",
                    "contradictory-structure-tags",
                    stable_id,
                    "road is simultaneously marked bridge and tunnel",
                )
            )
        if bridge and max(from_level, to_level) < 0:
            self.diagnostics.append(
                VerticalDiagnostic(
                    "error",
                    "bridge-below-grade",
                    stable_id,
                    f"bridge carries below-grade level endpoints {from_level}, {to_level}",
                )
            )
        if tunnel and min(from_level, to_level) > 0:
            self.diagnostics.append(
                VerticalDiagnostic(
                    "error",
                    "tunnel-above-grade",
                    stable_id,
                    f"tunnel carries above-grade level endpoints {from_level}, {to_level}",
                )
            )
        structure_kind = road_structure_kind(road, from_level, to_level)
        needs_clearance_envelope = (
            structure_kind in {"bridge", "tunnel"}
            and from_level == 0
            and to_level == 0
        )
        inferred = needs_clearance_envelope
        if needs_clearance_envelope:
            self.diagnostics.append(
                VerticalDiagnostic(
                    "warning",
                    "inferred-structure-clearance",
                    stable_id,
                    f"{structure_kind} endpoints are at grade or lack numeric separation; using a continuous {DEFAULT_LEVEL_SEPARATION_M:.1f} m maximum mid-span clearance envelope",
                )
            )
        path_profiles = tuple(
            _build_path_profile(
                road,
                path,
                self.elevation,
                from_level,
                to_level,
                structure_kind,
                self.diagnostics,
                clearance_envelope_m=(
                    DEFAULT_LEVEL_SEPARATION_M if needs_clearance_envelope else 0.0
                ),
            )
            for path in road.paths
            if len(path) >= 2
        )
        if not path_profiles:
            self.diagnostics.append(
                VerticalDiagnostic(
                    "error", "empty-road-profile", stable_id, "road has no path with at least two points"
                )
            )
        return RoadVerticalProfile(
            road=road,
            paths=path_profiles,
            from_level=from_level,
            to_level=to_level,
            level_source=level_source,
            structure_kind=structure_kind,
            inferred_structure_clearance=inferred,
        )

    def _associate_surface(self, surface: RoadSurface) -> SurfaceVerticalAssociation:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union

        stable_id = f"{surface.provenance.source_key}:{surface.source_id}"
        polygons = [
            Polygon(
                [(point.x, point.y) for point in polygon.outer],
                [[(point.x, point.y) for point in ring] for ring in polygon.holes],
            )
            for polygon in surface.polygons
        ]
        geometry = unary_union(polygons)
        if geometry.is_empty or self._road_tree is None:
            return SurfaceVerticalAssociation(None, "terrain-only")

        candidate_indices = list(self._road_tree.query(geometry))
        scored: dict[int, tuple[float, RoadVerticalProfile]] = {}
        for index in candidate_indices:
            profile = self._indexed_profiles[int(index)]
            line = self._road_geometries[int(index)]
            overlap = line.intersection(geometry).length
            if overlap <= 1e-6:
                continue
            key = id(profile)
            previous = scored.get(key)
            if previous is None:
                scored[key] = (overlap, profile)
            else:
                scored[key] = (previous[0] + overlap, profile)
        if not scored:
            return SurfaceVerticalAssociation(None, "terrain-only")

        ranked = sorted(scored.values(), key=lambda item: (-item[0], item[1].stable_id))
        top_score, top_profile = ranked[0]
        top_signature = (
            top_profile.from_level,
            top_profile.to_level,
            top_profile.structure_kind,
        )
        conflicting = [
            profile
            for score, profile in ranked[1:]
            if score >= top_score * 0.60
            and (profile.from_level, profile.to_level, profile.structure_kind)
            != top_signature
        ]
        if conflicting:
            ids = tuple(profile.stable_id for profile in [top_profile, *conflicting])
            self.diagnostics.append(
                VerticalDiagnostic(
                    "error",
                    "ambiguous-roadbed-vertical-topology",
                    stable_id,
                    "roadbed overlaps similarly strong centerlines at different vertical topologies: "
                    + ", ".join(ids),
                )
            )
            return SurfaceVerticalAssociation(top_profile, "unresolved", ids)
        return SurfaceVerticalAssociation(top_profile, "resolved")

    def road_profile(self, road: RoadCenterline) -> RoadVerticalProfile:
        return self._profiles[id(road)]

    def road_elevation(self, road: RoadCenterline, x: float, y: float) -> float:
        return self.road_profile(road).elevation_at(x, y)

    def surface_association(self, surface: RoadSurface) -> SurfaceVerticalAssociation:
        return self._surface_associations[id(surface)]

    def surface_elevation(self, surface: RoadSurface, x: float, y: float) -> float:
        association = self.surface_association(surface)
        profile = association.road_profile
        if profile is not None and profile.is_structured:
            return profile.elevation_at(x, y)
        sampled = self.elevation.sample(x, y)
        if sampled is None:
            stable_id = f"{surface.provenance.source_key}:{surface.source_id}"
            self.diagnostics.append(
                VerticalDiagnostic(
                    "error",
                    "missing-elevation-sample",
                    stable_id,
                    f"DEM has no surface sample at ({x:.3f}, {y:.3f})",
                )
            )
            return 0.0
        return sampled

    def diagnostics_payload(self) -> list[dict[str, str]]:
        return [diagnostic.as_dict() for diagnostic in self.diagnostics]
