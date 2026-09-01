from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Callable, Iterable, Mapping

ROADBED_RESOURCE = "https://data.cityofnewyork.us/resource/i36f-5ih7.geojson"
CENTERLINE_RESOURCE = "https://data.cityofnewyork.us/resource/inkn-q76z.geojson"
PAGE_SIZE = 25_000
NYC_BOUNDS_WGS84 = (-74.2591, 40.4774, -73.7002, 40.9176)
NYC_BOROUGH_CODES = {"1", "2", "3", "4", "5"}

ROADBED_PROPERTIES = (
    "source_id",
    "feat_code",
    "sub_code",
    "status",
    "shape_leng",
    "shape_area",
)
CENTERLINE_PROPERTIES = (
    "physicalid",
    "bphys_id",
    "boroughcode",
    "borough_code",
    "borough_indicator",
    "status",
    "trafdir",
    "rw_type",
    "streetwidth",
    "street_width",
    "from_level_code",
    "to_level_code",
    "number_travel_lanes",
    "number_park_lanes",
    "number_total_lanes",
    "number_total_lane",
    "full_street_name",
    "street_name",
    "street_name_label",
    "stname_label",
    "segment_type",
    "segmentlength",
    "segment_length",
    "objectid",
    # Legacy/truncated aliases retained for archived snapshots.
    "streetwidt",
    "from_level",
    "to_level_c",
    "number_tra",
    "number_par",
    "number_tot",
    "full_stree",
    "stname_lab",
    "segment_ty",
    "boroughcod",
    "boroughind",
    "bphysid",
)

FetchJson = Callable[[str], Mapping[str, Any]]


def page_url(base_url: str, *, limit: int, offset: int, order: str) -> str:
    if limit <= 0 or offset < 0:
        raise ValueError("invalid Socrata pagination")
    query = urllib.parse.urlencode(
        {"$limit": str(limit), "$offset": str(offset), "$order": order}
    )
    return f"{base_url}?{query}"


def download_json(url: str) -> Mapping[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Ny-drive citywide compiler/0.1"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def download_feature_collection(
    base_url: str,
    *,
    order: str,
    page_size: int = PAGE_SIZE,
    fetch: FetchJson = download_json,
) -> dict[str, Any]:
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        payload = fetch(page_url(base_url, limit=page_size, offset=offset, order=order))
        if payload.get("type") != "FeatureCollection":
            raise ValueError("Socrata GeoJSON response was not a FeatureCollection")
        page = list(payload.get("features") or [])
        features.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return {"type": "FeatureCollection", "features": features}


def _property_value(properties: Mapping[str, Any], *names: str):
    lowered = {str(key).lower(): value for key, value in properties.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def compact_collection(
    collection: Mapping[str, Any],
    *,
    keep_properties: Iterable[str],
    stable_property: str,
) -> dict[str, Any]:
    if collection.get("type") != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection")
    keep = tuple(keep_properties)
    compacted: list[dict[str, Any]] = []
    for feature in collection.get("features") or []:
        geometry = feature.get("geometry")
        if not isinstance(geometry, Mapping):
            continue
        properties = feature.get("properties") or {}
        if not isinstance(properties, Mapping):
            properties = {}
        lowered = {str(key).lower(): value for key, value in properties.items()}
        kept = {name: lowered[name.lower()] for name in keep if name.lower() in lowered}
        compacted.append(
            {
                "type": "Feature",
                "id": feature.get("id"),
                "properties": kept,
                "geometry": geometry,
            }
        )

    def sort_key(feature: Mapping[str, Any]):
        properties = feature.get("properties") or {}
        stable = _property_value(properties, stable_property)
        object_id = _property_value(properties, "objectid")
        geometry = json.dumps(feature.get("geometry"), sort_keys=True, separators=(",", ":"))
        return (str(stable or ""), str(object_id or ""), geometry)

    compacted.sort(key=sort_key)
    return {"type": "FeatureCollection", "features": compacted}


def _only_nyc_boroughs(collection: Mapping[str, Any]) -> dict[str, Any]:
    features = []
    for feature in collection.get("features") or []:
        properties = feature.get("properties") or {}
        code = _property_value(
            properties,
            "boroughcode",
            "borough_code",
            "boroughcod",
            "borocode",
            "borough_indicator",
            "boroughind",
        )
        if str(code or "").strip() in NYC_BOROUGH_CODES:
            features.append(feature)
    return {"type": "FeatureCollection", "features": features}


def build_citywide_snapshot(
    *,
    roadbed_revision: str,
    centerline_revision: str,
    page_size: int = PAGE_SIZE,
    fetch: FetchJson = download_json,
) -> dict[str, Any]:
    roadbed_raw = download_feature_collection(
        ROADBED_RESOURCE,
        order="source_id ASC",
        page_size=page_size,
        fetch=fetch,
    )
    centerline_raw = download_feature_collection(
        CENTERLINE_RESOURCE,
        order="bphys_id ASC, objectid ASC",
        page_size=page_size,
        fetch=fetch,
    )
    roadbed = compact_collection(
        roadbed_raw,
        keep_properties=ROADBED_PROPERTIES,
        stable_property="source_id",
    )
    centerline = _only_nyc_boroughs(
        compact_collection(
            centerline_raw,
            keep_properties=CENTERLINE_PROPERTIES,
            stable_property="bphys_id",
        )
    )
    return {
        "schema_version": 1,
        "name": "nyc-five-boroughs",
        "scope": "nyc-five-boroughs",
        "bounds_wgs84": list(NYC_BOUNDS_WGS84),
        "sources": {
            "roadbed": {
                "dataset_id": "i36f-5ih7",
                "data_revision": roadbed_revision,
                "resource_url": ROADBED_RESOURCE,
                "order": "source_id ASC",
            },
            "centerline": {
                "dataset_id": "inkn-q76z",
                "data_revision": centerline_revision,
                "resource_url": CENTERLINE_RESOURCE,
                "order": "bphys_id ASC, objectid ASC",
                "borough_filter": "NYC borough codes 1-5",
            },
        },
        "roadbed": roadbed,
        "centerline": centerline,
    }
