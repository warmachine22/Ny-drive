import json
from pathlib import Path

from nydrive_map_compiler.adapters.osm_overpass import normalize_overpass
from nydrive_map_compiler.model import Directionality

FIXTURE = Path(__file__).parent / "fixtures" / "osm_overpass.json"


def test_osm_semantics_are_normalized_without_browser_gis():
    payload = json.loads(FIXTURE.read_text())
    road = normalize_overpass(payload, source_revision="2026-08-30T00:00:00Z")[0]
    assert road.source_id == "77"
    assert road.name == "TEST AVENUE"
    assert road.semantics.directionality is Directionality.FORWARD
    assert road.semantics.lanes == 3
    assert road.semantics.lanes_forward == 3
    assert road.semantics.width_m == 11.5
    assert road.semantics.road_class == "primary"
    assert road.semantics.bridge is True
    assert road.semantics.tunnel is False
    assert road.semantics.layer == 1
    assert road.paths[0][0].x == 0.0
    assert road.paths[0][0].y == 0.0
