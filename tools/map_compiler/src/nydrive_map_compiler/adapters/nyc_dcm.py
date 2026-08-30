from __future__ import annotations

from typing import Any, Mapping

from shapely.geometry import shape

from ..crs import transform_geometry
from ..geometry import line_paths
from ..model import RoadCenterline, RoadSemantics, SourceProvenance
from .common import first, parse_dcm_width_m, scalar_properties

SOURCE_KEY = "nyc-dcm-street-centerline"
NATIVE_CRS = "EPSG:2263"


def normalize_dcm_feature(
    feature: Mapping[str, Any],
    *,
    source_crs: str = NATIVE_CRS,
    source_revision: str | None = None,
) -> RoadCenterline:
    properties = feature.get("properties") or {}
    raw_geometry = feature.get("geometry")
    if not isinstance(properties, Mapping) or not isinstance(raw_geometry, Mapping):
        raise ValueError("DCM feature must contain GeoJSON properties and geometry")

    source_id = str(first(properties, "OBJECTID", "objectid", default=feature.get("id", "unknown")))
    geometry = transform_geometry(shape(raw_geometry), source_crs)
    # The current shapefile metadata exposes the ten-character DBF field name
    # `Streetwidt`; older exports/FGDB views expose `Streetwidth`. Accept both
    # explicitly so a source refresh does not silently discard mapped widths.
    width = parse_dcm_width_m(
        first(properties, "Streetwidt", "Streetwidth", "streetwidth", "Street_Width")
    )
    semantics = RoadSemantics(width_m=width, road_class=first(properties, "Route_Type", "route_type"))
    return RoadCenterline(
        source_id=source_id,
        paths=line_paths(geometry),
        name=first(properties, "Street_NM", "street_nm"),
        borough=first(properties, "Borough", "borough"),
        feature_type=first(properties, "Feat_Type", "feat_type"),
        route_type=first(properties, "Route_Type", "route_type"),
        roadway_type=first(properties, "RoadwayType", "roadwaytype"),
        build_status=first(properties, "Build_Status", "build_status"),
        semantics=semantics,
        provenance=SourceProvenance(SOURCE_KEY, source_id, source_crs, source_revision),
        source_properties=scalar_properties(properties),
    )


def normalize_dcm_geojson(
    collection: Mapping[str, Any],
    *,
    source_crs: str = NATIVE_CRS,
    source_revision: str | None = None,
) -> list[RoadCenterline]:
    if collection.get("type") != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection")
    return [
        normalize_dcm_feature(feature, source_crs=source_crs, source_revision=source_revision)
        for feature in collection.get("features", [])
    ]
