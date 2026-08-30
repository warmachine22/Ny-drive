from __future__ import annotations

import argparse
import base64
import gzip
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from shapely.geometry import box, mapping, shape

# Roughly Fifth Avenue to Park Avenue South and East 20th to East 28th:
# enough real Manhattan grid for a 20–30 block development fixture.
BOUNDS = (-73.9967, 40.7388, -73.9882, 40.7481)
ROADBED_RESOURCE = "https://data.cityofnewyork.us/resource/i36f-5ih7.geojson"
CENTERLINE_RESOURCE = "https://data.cityofnewyork.us/resource/inkn-q76z.geojson"


def bounded_url(base_url: str) -> str:
    left, bottom, right, top = BOUNDS
    params = {
        "$limit": "5000",
        "$where": f"within_box(the_geom,{top},{left},{bottom},{right})",
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def download_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "Ny-drive fixture compiler/0.1"})
    with urllib.request.urlopen(request, timeout=90) as response:
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
    # Socrata already performs the coarse bbox query. Intersect locally as a
    # second deterministic clipping pass so the committed snapshot has exact
    # fixture bounds independent of source feature extent.
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


def build_snapshot() -> dict[str, Any]:
    roadbed_url = bounded_url(ROADBED_RESOURCE)
    centerline_url = bounded_url(CENTERLINE_RESOURCE)
    roadbed = subset_feature_collection(
        download_json(roadbed_url),
        keep_properties=("source_id", "feat_code", "sub_code", "status"),
    )
    centerline = subset_feature_collection(
        download_json(centerline_url),
        keep_properties=(
            "physicalid",
            "status",
            "trafdir",
            "rw_type",
            "street_width",
            "from_level_code",
            "to_level_code",
            "number_travel_lanes",
            "number_park_lanes",
            "number_total_lane",
            "full_street_name",
            "street_name",
            "street_name_label",
            "segment_type",
            # Legacy/truncated aliases retained so archived snapshots remain readable.
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
    return {
        "schema_version": 1,
        "name": "flatiron-madison-square",
        "bounds_wgs84": list(BOUNDS),
        "sources": {
            "roadbed": {
                "dataset_id": "i36f-5ih7",
                "data_revision": "2024-04-24",
                "query_url": roadbed_url,
            },
            "centerline": {
                "dataset_id": "inkn-q76z",
                "data_revision": "2026-08-16",
                "query_url": centerline_url,
            },
        },
        "roadbed": roadbed,
        "centerline": centerline,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    snapshot = build_snapshot()
    raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    roadbed_count = len(snapshot["roadbed"]["features"])
    centerline_count = len(snapshot["centerline"]["features"])

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw + b"\n")
        print(
            f"wrote {args.output} roadbed={roadbed_count} centerline={centerline_count} json_bytes={len(raw)}"
        )
        return 0

    compressed = gzip.compress(raw, mtime=0)
    encoded = base64.b64encode(compressed).decode("ascii")
    print(
        f"fixture roadbed={roadbed_count} centerline={centerline_count} "
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
