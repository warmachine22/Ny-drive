from nydrive_map_compiler.adapters.nyc_cscl import normalize_cscl_feature
from nydrive_map_compiler.model import Directionality


def test_fixture_cscl_metadata_becomes_driving_semantics():
    feature = {
        "type": "Feature",
        "properties": {
            "physicalid": "1341",
            "trafdir": "TF",
            "rw_type": "1",
            "street_width": "46",
            "number_travel_lanes": "3",
            "number_park_lanes": "2",
            "full_street_name": "7 AVE",
            "from_level_code": "13",
            "to_level_code": "13",
            "status": "2",
        },
        "geometry": {
            "type": "LineString",
            "coordinates": [[-73.9956462, 40.7441068], [-73.9951552, 40.7447681]],
        },
    }
    road = normalize_cscl_feature(feature, source_revision="2026-08-16")
    assert road.source_id == "1341"
    assert road.name == "7 AVE"
    assert road.semantics.directionality is Directionality.REVERSE
    assert road.semantics.lanes == 3
    assert road.semantics.lanes_backward == 3
    assert road.semantics.lanes_forward is None
    assert 14.01 < road.semantics.width_m < 14.03
    assert road.source_properties["from_level_code"] == "13"
