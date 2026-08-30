from pyproj import Transformer

from nydrive_map_compiler.crs import PROJECT_CRS, WGS84, project_origin_xy, to_project_xy


def test_project_origin_is_zero():
    assert to_project_xy(-74.0060, 40.7128, WGS84) == (0.0, 0.0)


def test_epsg2263_us_survey_foot_is_converted_to_meters():
    # Compare two nearby points in the official DCM source CRS. The target CRS
    # uses the same State Plane zone in metres, so 1000 source US survey feet
    # should remain about 304.8006 metres after normalization.
    a = to_project_xy(987000.0, 212000.0, "EPSG:2263")
    b = to_project_xy(988000.0, 212000.0, "EPSG:2263")
    assert 304.7 < b[0] - a[0] < 304.9
    assert abs(b[1] - a[1]) < 0.05


def test_origin_matches_direct_pyproj_transform():
    direct = Transformer.from_crs(WGS84, PROJECT_CRS, always_xy=True).transform(-74.0060, 40.7128)
    assert project_origin_xy() == direct
