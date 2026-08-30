import json
from pathlib import Path

from nydrive_map_compiler.adapters.nyc_dcm import normalize_dcm_feature, normalize_dcm_geojson
from nydrive_map_compiler.adapters.nyc_roadbed import normalize_roadbed_geojson

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_roadbed_geojson_becomes_metric_surface():
    surface = normalize_roadbed_geojson(load("roadbed.geojson"), source_revision="2024-04-24")[0]
    assert surface.source_id == "1001"
    assert surface.feature_code == 2000
    assert surface.polygons[0].outer[0].x < 0
    assert surface.polygons[0].outer[2].x > 0
    assert surface.provenance.source_crs == "EPSG:4326"


def test_dcm_native_epsg2263_fields_are_preserved_and_width_becomes_meters():
    road = normalize_dcm_geojson(load("dcm_centerline.geojson"), source_revision="2025-10-31")[0]
    assert road.source_id == "42"
    assert road.name == "TEST STREET"
    assert road.borough == "Manhattan"
    assert road.route_type == "Major_street"
    assert 18.28 < road.semantics.width_m < 18.30
    assert 30.47 < road.paths[0][1].x - road.paths[0][0].x < 30.50
    assert road.provenance.source_crs == "EPSG:2263"


def test_dcm_accepts_legacy_full_streetwidth_alias():
    feature = load("dcm_centerline.geojson")["features"][0]
    feature["properties"]["Streetwidth"] = feature["properties"].pop("Streetwidt")
    road = normalize_dcm_feature(feature)
    assert 18.28 < road.semantics.width_m < 18.30
