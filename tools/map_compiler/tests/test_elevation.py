from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from nydrive_map_compiler.crs import project_origin_xy
from nydrive_map_compiler.model import (
    Point2D,
    Polygon2D,
    RoadCenterline,
    RoadSemantics,
    RoadSurface,
    SourceProvenance,
)
from nydrive_map_compiler.vertical import (
    ConstantElevationSampler,
    RasterElevationSampler,
    VerticalResolver,
    cscl_level_offset,
)


def road(
    source_id,
    coords,
    *,
    feature_type=None,
    bridge=False,
    tunnel=False,
    layer=0,
    from_level=None,
    to_level=None,
    road_class="street",
):
    props = {}
    if from_level is not None:
        props["from_level_code"] = str(from_level)
    if to_level is not None:
        props["to_level_code"] = str(to_level)
    return RoadCenterline(
        source_id=source_id,
        paths=(tuple(Point2D(*point) for point in coords),),
        name=source_id,
        borough=None,
        feature_type=feature_type,
        route_type=None,
        roadway_type=None,
        build_status=None,
        semantics=RoadSemantics(
            bridge=bridge,
            tunnel=tunnel,
            layer=layer,
            road_class=road_class,
        ),
        provenance=SourceProvenance("roads", source_id, "LOCAL"),
        source_properties=props,
    )


def surface(source_id, outer):
    return RoadSurface(
        source_id=source_id,
        polygons=(Polygon2D(tuple(Point2D(*point) for point in outer)),),
        feature_code=2000,
        sub_code=1,
        status="active",
        provenance=SourceProvenance("roadbed", source_id, "LOCAL"),
    )


def test_cscl_level_code_is_relative_to_at_grade_13():
    assert cscl_level_offset(13) == 0
    assert cscl_level_offset("14") == 1
    assert cscl_level_offset(12) == -1
    assert cscl_level_offset(26) == 13
    assert cscl_level_offset(99) is None


def test_bridge_tunnel_and_ramp_profiles_preserve_grade_separation():
    bridge = road(
        "bridge",
        [(-20, 0), (20, 0)],
        feature_type="3",
        from_level=14,
        to_level=14,
    )
    tunnel = road(
        "tunnel",
        [(0, -20), (0, 20)],
        feature_type="4",
        from_level=12,
        to_level=12,
    )
    ramp = road(
        "ramp",
        [(-20, 30), (20, 30)],
        feature_type="9",
        from_level=13,
        to_level=14,
    )
    resolver = VerticalResolver([], [bridge, tunnel, ramp], ConstantElevationSampler(10.0))
    assert abs(resolver.road_elevation(bridge, 0, 0) - 15.0) < 1e-9
    assert abs(resolver.road_elevation(tunnel, 0, 0) - 5.0) < 1e-9
    assert abs(resolver.road_elevation(ramp, -20, 30) - 10.0) < 1e-9
    assert abs(resolver.road_elevation(ramp, 20, 30) - 15.0) < 1e-9
    assert abs(resolver.road_elevation(bridge, 0, 0) - resolver.road_elevation(tunnel, 0, 0)) >= 9.9


def test_at_grade_bridge_and_tunnel_endpoints_use_continuous_midspan_clearance():
    bridge = road(
        "bridge-at-grade-ends",
        [(-20, 0), (20, 0)],
        feature_type="3",
        from_level=13,
        to_level=13,
    )
    tunnel = road(
        "tunnel-at-grade-ends",
        [(0, -20), (0, 20)],
        feature_type="4",
        from_level=13,
        to_level=13,
    )
    resolver = VerticalResolver([], [bridge, tunnel], ConstantElevationSampler(10.0))
    assert resolver.road_elevation(bridge, -20, 0) == 10.0
    assert resolver.road_elevation(bridge, 20, 0) == 10.0
    assert resolver.road_elevation(tunnel, 0, -20) == 10.0
    assert resolver.road_elevation(tunnel, 0, 20) == 10.0
    assert resolver.road_elevation(bridge, 0, 0) >= 14.9
    assert resolver.road_elevation(tunnel, 0, 0) <= 5.1
    inferred = [item for item in resolver.diagnostics if item.code == "inferred-structure-clearance"]
    assert len(inferred) == 2


def test_surface_association_uses_longitudinal_overlap_not_crossing_proximity():
    bridge = road(
        "bridge",
        [(-50, 0), (50, 0)],
        feature_type="3",
        from_level=14,
        to_level=14,
    )
    street = road("street", [(0, -50), (0, 50)], from_level=13, to_level=13)
    bridge_surface = surface(
        "bridge-deck",
        [(-50, -4), (50, -4), (50, 4), (-50, 4), (-50, -4)],
    )
    resolver = VerticalResolver(
        [bridge_surface],
        [bridge, street],
        ConstantElevationSampler(10.0),
    )
    association = resolver.surface_association(bridge_surface)
    assert association.status == "resolved"
    assert association.road_profile is not None
    assert association.road_profile.road.source_id == "bridge"
    assert abs(resolver.surface_elevation(bridge_surface, 0, 0) - 15.0) < 1e-9


def test_ambiguous_surface_levels_are_diagnostic_instead_of_silently_flattened():
    upper = road("upper", [(-20, 0), (20, 0)], from_level=14, to_level=14)
    lower = road("lower", [(-20, 1), (20, 1)], from_level=13, to_level=13)
    shared = surface(
        "shared",
        [(-25, -3), (25, -3), (25, 4), (-25, 4), (-25, -3)],
    )
    resolver = VerticalResolver([shared], [upper, lower], ConstantElevationSampler(0.0))
    association = resolver.surface_association(shared)
    assert association.status == "unresolved"
    assert any(item.code == "ambiguous-roadbed-vertical-topology" for item in resolver.diagnostics)


def test_raster_sampler_reads_project_local_coordinates_and_converts_us_survey_feet(
    tmp_path: Path,
):
    ox, oy = project_origin_xy()
    path = tmp_path / "dem.tif"
    data = np.full((4, 4), 100.0, dtype="float32")
    transform = from_origin(ox - 2, oy + 2, 1, 1)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=4,
        height=4,
        count=1,
        dtype="float32",
        crs="EPSG:32118",
        transform=transform,
        nodata=-9999.0,
    ) as dataset:
        dataset.write(data, 1)
    with RasterElevationSampler([path], vertical_units="us_survey_foot") as sampler:
        sampled = sampler.sample(0.0, 0.0)
    assert sampled is not None
    assert abs(sampled - 30.48006096012192) < 1e-6
