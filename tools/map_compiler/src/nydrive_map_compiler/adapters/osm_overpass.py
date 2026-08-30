from __future__ import annotations

from typing import Any, Mapping

from ..crs import to_project_xy
from ..model import Directionality, Point2D, RoadCenterline, RoadSemantics, SourceProvenance
from .common import as_bool_tag, as_int, parse_osm_width_m, scalar_properties

SOURCE_KEY = "openstreetmap"


def _direction(tags: Mapping[str, Any]) -> Directionality:
    value = str(tags.get("oneway", "")).lower()
    if value == "-1":
        return Directionality.REVERSE
    if value in {"yes", "true", "1"} or (not value and tags.get("junction") == "roundabout"):
        return Directionality.FORWARD
    return Directionality.BOTH


def normalize_overpass(payload: Mapping[str, Any], *, source_revision: str | None = None) -> list[RoadCenterline]:
    elements = payload.get("elements", [])
    nodes: dict[int, tuple[float, float]] = {}
    for element in elements:
        if element.get("type") == "node" and "lat" in element and "lon" in element:
            nodes[int(element["id"])] = (float(element["lon"]), float(element["lat"]))

    roads: list[RoadCenterline] = []
    for element in elements:
        if element.get("type") != "way":
            continue
        tags = element.get("tags") or {}
        if not isinstance(tags, Mapping) or not tags.get("highway"):
            continue
        coords = []
        for node_id in element.get("nodes", []):
            lonlat = nodes.get(int(node_id))
            if lonlat is None:
                raise ValueError(f"OSM way {element.get('id')} references missing node {node_id}")
            x, y = to_project_xy(*lonlat, source_crs="EPSG:4326")
            coords.append(Point2D(x, y))
        if len(coords) < 2:
            continue

        source_id = str(element["id"])
        semantics = RoadSemantics(
            directionality=_direction(tags),
            lanes=as_int(tags.get("lanes")),
            lanes_forward=as_int(tags.get("lanes:forward")),
            lanes_backward=as_int(tags.get("lanes:backward")),
            width_m=parse_osm_width_m(tags.get("width")),
            road_class=str(tags.get("highway")) if tags.get("highway") is not None else None,
            bridge=as_bool_tag(tags.get("bridge")),
            tunnel=as_bool_tag(tags.get("tunnel")),
            layer=as_int(tags.get("layer")) or 0,
            tags=scalar_properties(tags),
        )
        roads.append(
            RoadCenterline(
                source_id=source_id,
                paths=(tuple(coords),),
                name=str(tags["name"]) if tags.get("name") else None,
                borough=None,
                feature_type=None,
                route_type=None,
                roadway_type=None,
                build_status=None,
                semantics=semantics,
                provenance=SourceProvenance(SOURCE_KEY, source_id, "EPSG:4326", source_revision),
                source_properties=scalar_properties(tags),
            )
        )
    return roads
