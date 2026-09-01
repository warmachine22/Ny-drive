from __future__ import annotations

import urllib.parse

from nydrive_map_compiler.acquisition import build_citywide_snapshot
from nydrive_map_compiler.citywide import RouteAuditSpec, audit_citywide, build_road_graph, compile_citywide_snapshot
from nydrive_map_compiler.model import Directionality, Point2D, RoadCenterline, RoadSemantics, SourceProvenance
from nydrive_map_compiler.vertical import ConstantElevationSampler


def _line_feature(index: int, borough_code: int, start, end, *, from_level="13", to_level="13", segment_type="1"):
    return {
        "type": "Feature",
        "properties": {
            "physicalid": str(index),
            "bphys_id": f"{borough_code}{index:05d}",
            "borough_code": str(borough_code),
            "trafdir": "",
            "rw_type": "1",
            "street_width": "40",
            "number_travel_lanes": "2",
            "full_street_name": f"TEST ROAD {index}",
            "from_level_code": from_level,
            "to_level_code": to_level,
            "segment_type": segment_type,
            "status": "2",
        },
        "geometry": {"type": "LineString", "coordinates": [list(start), list(end)]},
    }


def _roadbed_feature(index: int, start, end):
    x0, y0 = start
    x1, y1 = end
    half = 0.000025
    return {
        "type": "Feature",
        "properties": {
            "source_id": str(index),
            "feat_code": "2800",
            "sub_code": "280000",
            "status": "1",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [x0, y0 - half],
                [x1, y1 - half],
                [x1, y1 + half],
                [x0, y0 + half],
                [x0, y0 - half],
            ]],
        },
    }


def _five_borough_snapshot():
    points = [
        (-74.010, 40.700),
        (-74.005, 40.700),
        (-74.000, 40.700),
        (-73.995, 40.700),
        (-73.990, 40.700),
        (-73.985, 40.700),
    ]
    specs = [
        (1, "13", "14", "9"),
        (3, "14", "14", "3"),
        (4, "14", "13", "9"),
        (2, "13", "13", "4"),
        (5, "13", "13", "1"),
    ]
    centerline = [
        _line_feature(index + 1, borough, points[index], points[index + 1], from_level=from_level, to_level=to_level, segment_type=segment_type)
        for index, (borough, from_level, to_level, segment_type) in enumerate(specs)
    ]
    roadbed = [
        _roadbed_feature(index + 1, points[index], points[index + 1])
        for index in range(5)
    ]
    return {
        "schema_version": 1,
        "name": "synthetic-five-boroughs",
        "bounds_wgs84": [-74.011, 40.699, -73.984, 40.701],
        "sources": {
            "roadbed": {"data_revision": "test"},
            "centerline": {"data_revision": "test"},
        },
        "roadbed": {"type": "FeatureCollection", "features": roadbed},
        "centerline": {"type": "FeatureCollection", "features": centerline},
    }, points


def test_citywide_compile_covers_all_boroughs_and_long_route():
    snapshot, points = _five_borough_snapshot()
    route = RouteAuditSpec(
        "synthetic-cross-city",
        (points[0], points[-1]),
        ("Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"),
        max_snap_m=50.0,
    )
    manifest, tiles = compile_citywide_snapshot(
        snapshot,
        elevation_sampler=ConstantElevationSampler(10.0),
        route_audits=(route,),
    )

    assert manifest["schema_version"] == 2
    assert manifest["scope"] == "nyc-five-boroughs"
    assert manifest["input_counts"] == {"roadbed": 5, "centerline": 5, "buildings": 0}
    assert manifest["tile_count"] >= 5
    assert len(tiles) == manifest["tile_count"]

    audit = manifest["citywide_audit"]
    assert audit["borough_coverage"]["missing"] == []
    assert all(audit["borough_coverage"]["road_counts"].values())
    assert audit["topology"]["cross_borough_node_count"] >= 4
    assert audit["topology"]["cross_tile_road_count"] >= 1
    assert audit["topology"]["structure_counts"]["bridge"] >= 1
    assert audit["topology"]["structure_counts"]["ramp"] >= 1
    assert audit["topology"]["structure_counts"]["tunnel"] >= 1
    assert audit["routes"][0]["connected"] is True
    assert audit["routes"][0]["directionally_connected"] is True
    assert set(audit["routes"][0]["path_boroughs"]) == {
        "Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"
    }


def _normalized_road(source_id: str, start, end, *, from_level: str, to_level: str):
    return RoadCenterline(
        source_id=source_id,
        paths=((Point2D(*start), Point2D(*end)),),
        name=source_id,
        borough="Manhattan",
        feature_type="1",
        route_type="1",
        roadway_type="1",
        build_status="2",
        semantics=RoadSemantics(directionality=Directionality.BOTH),
        provenance=SourceProvenance("test", source_id, "EPSG:32118", "test"),
        source_properties={"from_level_code": from_level, "to_level_code": to_level},
    )


def test_graph_does_not_join_coincident_endpoints_at_different_vertical_levels():
    lower = _normalized_road("lower", (0.0, 0.0), (100.0, 0.0), from_level="13", to_level="13")
    upper = _normalized_road("upper", (100.0, 0.0), (200.0, 0.0), from_level="14", to_level="14")
    graph = build_road_graph([lower, upper])

    assert len(graph.edges) == 2
    assert len(graph.node_xy) == 4
    assert graph.edges[0].end_node != graph.edges[1].start_node


def test_citywide_audit_surfaces_missing_borough_and_duplicate_ids():
    first = _normalized_road("duplicate", (0.0, 0.0), (100.0, 0.0), from_level="13", to_level="13")
    second = _normalized_road("duplicate", (100.0, 0.0), (200.0, 0.0), from_level="13", to_level="13")
    audit = audit_citywide([first, second], [], {}, route_audits=())

    assert "Brooklyn" in audit["borough_coverage"]["missing"]
    assert audit["invalid_topology"]["duplicate_road_id_count"] == 1
    assert audit["invalid_topology"]["duplicate_road_id_sample"] == ["test:duplicate"]


def test_citywide_acquisition_paginates_and_sorts_deterministically():
    roadbed = [
        {"type": "Feature", "properties": {"source_id": value, "status": "1"}, "geometry": {"type": "Polygon", "coordinates": []}}
        for value in ("3", "1", "2")
    ]
    centerline = [
        {"type": "Feature", "properties": {"bphys_id": value, "physicalid": value, "borough_code": "1", "objectid": value}, "geometry": {"type": "LineString", "coordinates": []}}
        for value in ("30", "10", "20")
    ]
    calls = []

    def fake_fetch(url: str):
        calls.append(url)
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        offset = int(query["$offset"][0])
        limit = int(query["$limit"][0])
        source = roadbed if "i36f-5ih7" in parsed.path else centerline
        return {"type": "FeatureCollection", "features": source[offset : offset + limit]}

    snapshot = build_citywide_snapshot(
        roadbed_revision="roadbed-test",
        centerline_revision="centerline-test",
        page_size=2,
        fetch=fake_fetch,
    )

    assert len(calls) == 4
    assert [item["properties"]["source_id"] for item in snapshot["roadbed"]["features"]] == ["1", "2", "3"]
    assert [item["properties"]["bphys_id"] for item in snapshot["centerline"]["features"]] == ["10", "20", "30"]
    assert snapshot["sources"]["roadbed"]["data_revision"] == "roadbed-test"
    assert snapshot["sources"]["centerline"]["data_revision"] == "centerline-test"
