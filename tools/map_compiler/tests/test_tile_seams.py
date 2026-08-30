from collections import Counter

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from nydrive_map_compiler.model import (
    Directionality,
    Point2D,
    Polygon2D,
    RoadCenterline,
    RoadSemantics,
    RoadSurface,
    SourceProvenance,
)
from nydrive_map_compiler.tiling import compile_tiles


def _global_surface_polygons(tiles):
    polygons = []
    for tile in tiles.values():
        ox, oy = tile["origin_m"]
        for surface in tile["road_surfaces"]:
            for polygon in surface["polygons"]:
                outer = [(x + ox, y + oy) for x, y in polygon["outer"]]
                holes = [[(x + ox, y + oy) for x, y in ring] for ring in polygon["holes"]]
                polygons.append(Polygon(outer, holes))
    return polygons


def test_tile_surface_seam_reconstructs_without_gap():
    original = Polygon([(250.0, 10.0), (270.0, 10.0), (270.0, 30.0), (250.0, 30.0)])
    surface = RoadSurface(
        source_id="surface-1",
        polygons=(Polygon2D(tuple(Point2D(x, y) for x, y in original.exterior.coords)),),
        feature_code=2000,
        sub_code=1,
        status="active",
        provenance=SourceProvenance("test-roadbed", "surface-1", "LOCAL"),
    )
    tiles = compile_tiles([surface], [])
    stable_ids = [item["stable_id"] for tile in tiles.values() for item in tile["road_surfaces"]]
    assert Counter(stable_ids)["test-roadbed:surface-1"] == 2
    reconstructed = unary_union(_global_surface_polygons(tiles))
    assert reconstructed.symmetric_difference(original).area < 1e-6


def test_tile_centerline_seam_preserves_length_and_stable_id():
    original = LineString([(250.0, 40.0), (270.0, 40.0)])
    road = RoadCenterline(
        source_id="road-1",
        paths=((Point2D(250.0, 40.0), Point2D(270.0, 40.0)),),
        name="SEAM TEST",
        borough=None,
        feature_type=None,
        route_type=None,
        roadway_type=None,
        build_status=None,
        semantics=RoadSemantics(directionality=Directionality.FORWARD, lanes=2),
        provenance=SourceProvenance("test-centerline", "road-1", "LOCAL"),
    )
    tiles = compile_tiles([], [road])
    lengths = []
    stable_ids = []
    for tile in tiles.values():
        ox, oy = tile["origin_m"]
        for item in tile["roads"]:
            stable_ids.append(item["stable_id"])
            for path in item["paths"]:
                lengths.append(LineString([(x + ox, y + oy) for x, y in path]).length)
    assert Counter(stable_ids)["test-centerline:road-1"] == 2
    assert abs(sum(lengths) - original.length) < 1e-6
