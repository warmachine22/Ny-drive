from __future__ import annotations

from nydrive_map_compiler.adapters.nyc_buildings import normalize_building_feature
from nydrive_map_compiler.fixture import compile_snapshot
from nydrive_map_compiler.vertical import ConstantElevationSampler


def _building_feature(source_id: str, *, height_roof=None, feature_code="2100"):
    properties = {
        "doitt_id": source_id,
        "bin": f"1{int(source_id):06d}",
        "feature_code": feature_code,
        "construction_year": "1920",
        "ground_elevation": "35",
    }
    if height_roof is not None:
        properties["height_roof"] = str(height_roof)
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-74.0055, 40.7134],
                [-74.0053, 40.7134],
                [-74.0053, 40.7136],
                [-74.0055, 40.7136],
                [-74.0055, 40.7134],
            ]],
        },
    }


def test_source_height_is_converted_and_missing_height_is_explicit_fallback():
    measured = normalize_building_feature(_building_feature("1", height_roof=100))
    fallback = normalize_building_feature(_building_feature("2"))

    assert measured is not None
    assert measured.height_m == 30.48
    assert measured.height_source == "nyc-height-roof"
    assert measured.source_ground_elevation_m is not None
    assert abs(measured.source_ground_elevation_m - 10.668) < 1e-9

    assert fallback is not None
    assert fallback.height_m > 0
    assert fallback.height_source == "deterministic-visual-fallback"


def test_placeholder_triangle_is_not_rendered_as_a_building():
    assert normalize_building_feature(_building_feature("3", feature_code="1003")) is None


def test_buildings_are_tiled_and_grounded_to_world_terrain_not_absolute_source_elevation():
    snapshot = {
        "name": "building-test",
        "bounds_wgs84": [-74.006, 40.713, -74.005, 40.714],
        "sources": {
            "roadbed": {"data_revision": "test"},
            "centerline": {"data_revision": "test"},
            "buildings": {"data_revision": "test"},
        },
        "roadbed": {"type": "FeatureCollection", "features": []},
        "centerline": {"type": "FeatureCollection", "features": []},
        "buildings": {
            "type": "FeatureCollection",
            "features": [_building_feature("10", height_roof=50), _building_feature("11")],
        },
    }
    manifest, tiles = compile_snapshot(snapshot, elevation_sampler=ConstantElevationSampler(7.25))

    assert manifest["schema_version"] == 2
    assert manifest["input_counts"] == {"roadbed": 0, "centerline": 0, "buildings": 2}
    assert manifest["scenery"]["building_count"] == 2
    assert manifest["scenery"]["source_height_count"] == 1
    assert manifest["scenery"]["fallback_height_count"] == 1
    assert manifest["scenery"]["collision_policy"] == "visual-only"

    emitted = [building for tile in tiles.values() for building in tile["buildings"]]
    assert emitted
    assert {item["source_id"] for item in emitted} == {"10", "11"}
    assert {item["base_elevation_m"] for item in emitted} == {7.25}
    assert {item["base_elevation_source"] for item in emitted} == {"test-elevation"}
    # The source NAVD88 ground value is retained as provenance but not used to float
    # scenery above the active road/terrain coordinate system.
    assert all(item["source_ground_elevation_m"] == 10.668 for item in emitted)
