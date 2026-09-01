from __future__ import annotations

from typing import Any, Mapping

from shapely.geometry import shape

from ..crs import transform_geometry
from ..geometry import surface_polygons
from ..model import BuildingFootprint, SourceProvenance
from .common import as_int, first, scalar_properties

SOURCE_KEY = "nyc-building-footprints"
FOOT_TO_M = 0.3048
PLACEHOLDER_FEATURE_CODE = 1003
LOW_STRUCTURE_CODES = {1000, 1001, 1002, 1004, 1005, 2110, 5110}


def _as_positive_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def fallback_height_m(feature_code: int | None, footprint_area_m2: float) -> float:
    """Return a deterministic visual-massing height, never a claimed measurement."""
    if feature_code in LOW_STRUCTURE_CODES:
        return 4.5
    if footprint_area_m2 < 150.0:
        return 7.5
    if footprint_area_m2 >= 1_000.0:
        return 18.0
    return 12.0


def normalize_building_feature(
    feature: Mapping[str, Any],
    *,
    source_crs: str = "EPSG:4326",
    source_revision: str | None = None,
) -> BuildingFootprint | None:
    properties = feature.get("properties") or {}
    raw_geometry = feature.get("geometry")
    if not isinstance(properties, Mapping) or not isinstance(raw_geometry, Mapping):
        raise ValueError("Building feature must contain GeoJSON properties and geometry")

    feature_code = as_int(first(properties, "FEATURE_CODE", "feature_code", "feat_code"))
    if feature_code == PLACEHOLDER_FEATURE_CODE:
        return None

    source_id = str(
        first(
            properties,
            "DOITT_ID",
            "doitt_id",
            default=feature.get("id") or first(properties, "OBJECTID", "objectid", default="unknown"),
        )
    )
    geometry = transform_geometry(shape(raw_geometry), source_crs)
    polygons = surface_polygons(geometry)

    source_height_ft = _as_positive_float(first(properties, "HEIGHT_ROOF", "height_roof", "heightroof"))
    if source_height_ft is not None:
        height_m = source_height_ft * FOOT_TO_M
        height_source = "nyc-height-roof"
    else:
        height_m = fallback_height_m(feature_code, float(geometry.area))
        height_source = "deterministic-visual-fallback"

    source_ground_ft = _as_positive_float(
        first(properties, "GROUND_ELEVATION", "ground_elevation", "groundelev")
    )
    source_ground_m = source_ground_ft * FOOT_TO_M if source_ground_ft is not None else None

    construction_year = as_int(first(properties, "CONSTRUCTION_YEAR", "construction_year", "cnstrct_yr"))
    if construction_year == 0:
        construction_year = None

    bin_value = first(properties, "BIN", "bin")
    return BuildingFootprint(
        source_id=source_id,
        polygons=polygons,
        height_m=height_m,
        height_source=height_source,
        source_ground_elevation_m=source_ground_m,
        feature_code=feature_code,
        bin=str(bin_value) if bin_value not in (None, "") else None,
        name=first(properties, "NAME", "name"),
        construction_year=construction_year,
        provenance=SourceProvenance(SOURCE_KEY, source_id, source_crs, source_revision),
        source_properties=scalar_properties(properties),
    )


def normalize_building_geojson(
    collection: Mapping[str, Any],
    *,
    source_crs: str = "EPSG:4326",
    source_revision: str | None = None,
) -> list[BuildingFootprint]:
    if collection.get("type") != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection")
    result: list[BuildingFootprint] = []
    for feature in collection.get("features", []):
        building = normalize_building_feature(
            feature,
            source_crs=source_crs,
            source_revision=source_revision,
        )
        if building is not None:
            result.append(building)
    return result
