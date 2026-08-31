from __future__ import annotations

from typing import Any, Mapping

from shapely.geometry import shape

from ..crs import transform_geometry
from ..geometry import line_paths
from ..model import Directionality, RoadCenterline, RoadSemantics, SourceProvenance
from .common import as_int, first, parse_dcm_width_m, scalar_properties

SOURCE_KEY = "nyc-cscl-centerline"
SOURCE_CRS = "EPSG:4326"
BRIDGE_SEGMENT_TYPE = "3"
TUNNEL_SEGMENT_TYPE = "4"


def _directionality(value: Any) -> Directionality:
    code = str(value or "").strip().upper()
    if code == "FT":
        return Directionality.FORWARD
    if code == "TF":
        return Directionality.REVERSE
    return Directionality.BOTH


def normalize_cscl_feature(
    feature: Mapping[str, Any],
    *,
    source_crs: str = SOURCE_CRS,
    source_revision: str | None = None,
) -> RoadCenterline:
    properties = feature.get("properties") or {}
    raw_geometry = feature.get("geometry")
    if not isinstance(properties, Mapping) or not isinstance(raw_geometry, Mapping):
        raise ValueError("CSCL feature must contain GeoJSON properties and geometry")

    source_id = str(first(properties, "physicalid", "PHYSICALID", default=feature.get("id", "unknown")))
    directionality = _directionality(first(properties, "trafdir", "TRAFDIR"))
    travel_lanes = as_int(first(properties, "number_travel_lanes", "number_tra"))
    lanes_forward = travel_lanes if directionality is Directionality.FORWARD else None
    lanes_backward = travel_lanes if directionality is Directionality.REVERSE else None
    width_m = parse_dcm_width_m(first(properties, "street_width", "streetwidt"))
    road_class_value = first(properties, "rw_type", "RW_TYPE")
    segment_type = first(properties, "segment_type", "segment_ty")
    segment_type_code = str(segment_type).strip() if segment_type is not None else ""

    geometry = transform_geometry(shape(raw_geometry), source_crs)
    return RoadCenterline(
        source_id=source_id,
        paths=line_paths(geometry),
        name=first(properties, "full_street_name", "full_stree", "street_name_label", "stname_lab"),
        borough=None,
        feature_type=segment_type,
        route_type=str(road_class_value) if road_class_value is not None else None,
        roadway_type=str(road_class_value) if road_class_value is not None else None,
        build_status=first(properties, "status", "STATUS"),
        semantics=RoadSemantics(
            directionality=directionality,
            lanes=travel_lanes,
            lanes_forward=lanes_forward,
            lanes_backward=lanes_backward,
            width_m=width_m,
            road_class=str(road_class_value) if road_class_value is not None else None,
            bridge=segment_type_code == BRIDGE_SEGMENT_TYPE,
            tunnel=segment_type_code == TUNNEL_SEGMENT_TYPE,
            tags=scalar_properties(properties),
        ),
        provenance=SourceProvenance(SOURCE_KEY, source_id, source_crs, source_revision),
        source_properties=scalar_properties(properties),
    )


def normalize_cscl_geojson(
    collection: Mapping[str, Any],
    *,
    source_crs: str = SOURCE_CRS,
    source_revision: str | None = None,
) -> list[RoadCenterline]:
    if collection.get("type") != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection")
    return [
        normalize_cscl_feature(feature, source_crs=source_crs, source_revision=source_revision)
        for feature in collection.get("features", [])
    ]
