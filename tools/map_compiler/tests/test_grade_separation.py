from nydrive_map_compiler.model import (
    Point2D,
    Polygon2D,
    RoadCenterline,
    RoadSemantics,
    RoadSurface,
    SourceProvenance,
)
from nydrive_map_compiler.tiling import compile_tiles
from nydrive_map_compiler.vertical import ConstantElevationSampler, VerticalResolver


def _road(source_id, coords, *, feature_type=None, from_level=13, to_level=13):
    return RoadCenterline(
        source_id=source_id,
        paths=(tuple(Point2D(*point) for point in coords),),
        name=source_id,
        borough=None,
        feature_type=feature_type,
        route_type=None,
        roadway_type=None,
        build_status=None,
        semantics=RoadSemantics(),
        provenance=SourceProvenance("centerline", source_id, "LOCAL"),
        source_properties={
            "from_level_code": str(from_level),
            "to_level_code": str(to_level),
        },
    )


def _surface(source_id, outer):
    return RoadSurface(
        source_id=source_id,
        polygons=(Polygon2D(tuple(Point2D(*point) for point in outer)),),
        feature_code=2000,
        sub_code=1,
        status="active",
        provenance=SourceProvenance("roadbed", source_id, "LOCAL"),
    )


def test_elevation_bridge_profile_is_continuous_across_tile_seam():
    road = _road(
        "bridge",
        [(250, 40), (270, 40)],
        feature_type="3",
        from_level=14,
        to_level=14,
    )
    resolver = VerticalResolver([], [road], ConstantElevationSampler(8.0))
    tiles = compile_tiles([], [road], vertical=resolver)
    heights = []
    for tile in tiles.values():
        assert tile["schema_version"] == 2
        for item in tile["roads"]:
            for path in item["paths"]:
                for point in path:
                    if abs((tile["origin_m"][0] + point[0]) - 256.0) < 0.002:
                        heights.append(point[2])
    assert len(heights) == 2
    assert max(heights) - min(heights) < 1e-6
    assert heights[0] == 13.0


def test_bridge_and_tunnel_crossing_compile_at_distinct_heights():
    bridge = _road(
        "bridge",
        [(10, 100), (90, 100)],
        feature_type="3",
        from_level=14,
        to_level=14,
    )
    tunnel = _road(
        "tunnel",
        [(50, 60), (50, 140)],
        feature_type="4",
        from_level=12,
        to_level=12,
    )
    bridge_surface = _surface(
        "bridge-surface",
        [(10, 96), (90, 96), (90, 104), (10, 104), (10, 96)],
    )
    tunnel_surface = _surface(
        "tunnel-surface",
        [(46, 60), (54, 60), (54, 140), (46, 140), (46, 60)],
    )
    resolver = VerticalResolver(
        [bridge_surface, tunnel_surface],
        [bridge, tunnel],
        ConstantElevationSampler(10.0),
    )
    tiles = compile_tiles(
        [bridge_surface, tunnel_surface],
        [bridge, tunnel],
        vertical=resolver,
    )
    tile = next(iter(tiles.values()))
    road_heights = {item["source_id"]: item["paths"][0][0][2] for item in tile["roads"]}
    assert road_heights["bridge"] == 15.0
    assert road_heights["tunnel"] == 5.0
    assert road_heights["bridge"] - road_heights["tunnel"] == 10.0


def test_at_grade_bridge_endpoints_still_compile_a_separated_midspan_deck():
    bridge = _road(
        "bridge-at-grade-ends",
        [(10, 100), (110, 100)],
        feature_type="3",
        from_level=13,
        to_level=13,
    )
    street = _road(
        "cross-street",
        [(60, 50), (60, 150)],
        from_level=13,
        to_level=13,
    )
    bridge_surface = _surface(
        "bridge-at-grade-surface",
        [(10, 96), (110, 96), (110, 104), (10, 104), (10, 96)],
    )
    resolver = VerticalResolver(
        [bridge_surface],
        [bridge, street],
        ConstantElevationSampler(10.0),
    )
    tile = next(
        iter(compile_tiles([bridge_surface], [bridge, street], vertical=resolver).values())
    )
    bridge_item = next(item for item in tile["roads"] if item["source_id"] == bridge.source_id)
    street_item = next(item for item in tile["roads"] if item["source_id"] == street.source_id)
    bridge_heights = [point[2] for path in bridge_item["paths"] for point in path]
    street_heights = [point[2] for path in street_item["paths"] for point in path]
    surface_heights = [
        point[2]
        for polygon in tile["road_surfaces"][0]["polygons"]
        for point in polygon["outer"]
    ]
    assert bridge_heights[0] == 10.0
    assert bridge_heights[-1] == 10.0
    assert max(bridge_heights) > 14.0
    assert max(street_heights) == 10.0
    assert max(surface_heights) > 14.0
    assert any(
        item["code"] == "inferred-structure-clearance"
        for item in tile["vertical_diagnostics"]
    )


def test_grade_ramp_interpolates_between_at_grade_and_upper_level():
    ramp = _road(
        "ramp",
        [(0, 0), (100, 0)],
        feature_type="9",
        from_level=13,
        to_level=14,
    )
    resolver = VerticalResolver([], [ramp], ConstantElevationSampler(20.0))
    tile = next(iter(compile_tiles([], [ramp], vertical=resolver).values()))
    path = tile["roads"][0]["paths"][0]
    assert path[0][2] == 20.0
    assert path[-1][2] == 25.0
    assert tile["roads"][0]["ramp"] is True
