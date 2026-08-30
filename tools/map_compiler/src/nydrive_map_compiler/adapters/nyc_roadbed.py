from __future__ import annotations

from typing import Any, Mapping

from shapely.geometry import shape

from ..crs import transform_geometry
from ..geometry import surface_polygons
from ..model import RoadSurface, SourceProvenance
from .common import as_int, first, scalar_properties

SOURCE_KEY = "nyc-planimetrics-roadbed"


def normalize_roadbed_feature(
    feature: Mapping[str, Any],
    *,
    source_crs: str = "EPSG:4326",
    source_revision: str | None = None,
) -> RoadSurface:
    properties = feature.get("properties") or {}
    raw_geometry = feature.get("geometry")
    if not isinstance(properties, Mapping) or not isinstance(raw_geometry, Mapping):
        raise ValueError("Roadbed feature must contain GeoJSON properties and geometry")

    source_id = str(first(properties, "SOURCE_ID", "source_id", default=feature.get("id", "unknown")))
    geometry = transform_geometry(shape(raw_geometry), source_crs)
    return RoadSurface(
        source_id=source_id,
        polygons=surface_polygons(geometry),
        feature_code=as_int(first(properties, "FEAT_CODE", "feat_code")),
        sub_code=as_int(first(properties, "SUB_CODE", "sub_code")),
        status=first(properties, "STATUS", "status"),
        provenance=SourceProvenance(SOURCE_KEY, source_id, source_crs, source_revision),
        source_properties=scalar_properties(properties),
    )


def normalize_roadbed_geojson(
    collection: Mapping[str, Any],
    *,
    source_crs: str = "EPSG:4326",
    source_revision: str | None = None,
) -> list[RoadSurface]:
    if collection.get("type") != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection")
    return [
        normalize_roadbed_feature(feature, source_crs=source_crs, source_revision=source_revision)
        for feature in collection.get("features", [])
    ]
