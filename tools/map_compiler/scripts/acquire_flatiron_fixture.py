from __future__ import annotations

import base64
import gzip
import json
import sys
import urllib.request
from typing import Any

from shapely.geometry import box, mapping, shape

# Roughly Fifth Avenue to Park Avenue South and East 20th to East 28th:
# enough real Manhattan grid for a 20–30 block development fixture.
BOUNDS = (-73.9967, 40.7388, -73.9882, 40.7481)
ROADBED_URL = "https://data.cityofnewyork.us/api/v3/views/i36f-5ih7/query.geojson?accessType=DOWNLOAD"
CENTERLINE_URL = "https://data.cityofnewyork.us/api/v3/views/inkn-q76z/query.geojson?accessType=DOWNLOAD"


def download_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "Ny-drive fixture compiler/0.1"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def rounded_geometry(geometry) -> dict[str, Any]:
    def round_coords(value):
        if isinstance(value, (tuple, list)):
            if value and isinstance(value[0], (int, float)):
                return [round(float(number), 7) for number in value]
            return [round_coords(item) for item in value]
        return value

    result = mapping(geometry)
    result["coordinates"] = round_coords(result["coordinates"])
    return result


def subset_feature_collection(
    collection: dict[str, Any],
    *,
    keep_properties: tuple[str, ...],
) -> dict[str, Any]:
    clip = box(*BOUNDS)
    selected = []
    for feature in collection.get("features", []):
        raw_geometry = feature.get("geometry")
        if not raw_geometry:
            continue
        geometry = shape(raw_geometry)
        if geometry.is_empty or not geometry.intersects(clip):
            continue
        geometry = geometry.intersection(clip)
        if geometry.is_empty:
            continue
        properties = feature.get("properties") or {}
        lowered = {str(key).lower(): value for key, value in properties.items()}
        kept = {name: lowered.get(name.lower()) for name in keep_properties if name.lower() in lowered}
        selected.append(
            {
                "type": "Feature",
                "id": feature.get("id"),
                "properties": kept,
                "geometry": rounded_geometry(geometry),
            }
        )
    return {"type": "FeatureCollection", "features": selected}


def main() -> int:
    roadbed = subset_feature_collection(
        download_json(ROADBED_URL),
        keep_properties=("source_id", "feat_code", "sub_code", "status"),
    )
    centerline = subset_feature_collection(
        download_json(CENTERLINE_URL),
        keep_properties=(
            "physicalid",
            "status",
            "trafdir",
            "rw_type",
            "streetwidt",
            "from_level",
            "to_level_c",
            "number_tra",
            "number_par",
            "number_tot",
            "full_stree",
            "stname_lab",
            "segment_ty",
        ),
    )
    snapshot = {
        "schema_version": 1,
        "name": "flatiron-madison-square",
        "bounds_wgs84": list(BOUNDS),
        "sources": {
            "roadbed": {
                "dataset_id": "i36f-5ih7",
                "data_revision": "2024-04-24",
                "url": ROADBED_URL,
            },
            "centerline": {
                "dataset_id": "inkn-q76z",
                "data_revision": "2026-08-22",
                "url": CENTERLINE_URL,
            },
        },
        "roadbed": roadbed,
        "centerline": centerline,
    }
    raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(raw, mtime=0)
    encoded = base64.b64encode(compressed).decode("ascii")
    print(
        f"fixture roadbed={len(roadbed['features'])} centerline={len(centerline['features'])} "
        f"json_bytes={len(raw)} gzip_bytes={len(compressed)}",
        file=sys.stderr,
    )
    print("NYDRIVE_FIXTURE_B64_BEGIN")
    for index in range(0, len(encoded), 120):
        print(encoded[index : index + 120])
    print("NYDRIVE_FIXTURE_B64_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
