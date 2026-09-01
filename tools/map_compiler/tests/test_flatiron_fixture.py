import json
from pathlib import Path

from nydrive_map_compiler.fixture import compile_snapshot, write_compiled_fixture
from nydrive_map_compiler.tiling import TILE_SIZE_M, feature_tile_counts

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "fixtures" / "flatiron" / "source_snapshot.json"


def test_flatiron_fixture_compiles_real_official_snapshot():
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    manifest, tiles = compile_snapshot(snapshot)

    assert manifest["name"] == "flatiron-madison-square"
    assert manifest["input_counts"] == {"roadbed": 110, "centerline": 71, "buildings": 797}
    assert manifest["scenery"] == {
        "source_key": "nyc-building-footprints",
        "building_count": 797,
        "source_height_count": 796,
        "fallback_height_count": 1,
        "collision_policy": "visual-only",
    }
    assert 12 <= manifest["tile_count"] <= 30
    assert manifest["coordinate_system"]["tile_size_m"] == 256.0

    road_names = {road["name"] for tile in tiles.values() for road in tile["roads"] if road["name"]}
    assert "BROADWAY" in road_names
    assert "7 AVE" in road_names
    assert max(road["lanes"] or 0 for tile in tiles.values() for road in tile["roads"]) >= 4

    directions = {road["directionality"] for tile in tiles.values() for road in tile["roads"]}
    assert {"forward", "reverse", "both"}.issubset(directions)

    surface_counts = feature_tile_counts(tiles, "road_surfaces")
    road_counts = feature_tile_counts(tiles, "roads")
    building_counts = feature_tile_counts(tiles, "buildings")
    assert max(surface_counts.values()) >= 2
    assert max(road_counts.values()) >= 2
    assert max(building_counts.values()) >= 2

    tolerance = 0.002
    for tile in tiles.values():
        for collection in ("road_surfaces", "buildings"):
            for feature in tile.get(collection, []):
                for polygon in feature["polygons"]:
                    for ring in [polygon["outer"], *polygon["holes"]]:
                        assert all(-tolerance <= value <= TILE_SIZE_M + tolerance for point in ring for value in point[:2])
        for road in tile["roads"]:
            for path in road["paths"]:
                assert all(-tolerance <= value <= TILE_SIZE_M + tolerance for point in path for value in point[:2])


def test_flatiron_fixture_writer_is_byte_deterministic(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_manifest = write_compiled_fixture(SNAPSHOT, first)
    second_manifest = write_compiled_fixture(SNAPSHOT, second)
    assert first_manifest == second_manifest

    first_files = sorted(path.relative_to(first) for path in first.rglob("*.json"))
    second_files = sorted(path.relative_to(second) for path in second.rglob("*.json"))
    assert first_files == second_files
    for relative in first_files:
        assert (first / relative).read_bytes() == (second / relative).read_bytes()
