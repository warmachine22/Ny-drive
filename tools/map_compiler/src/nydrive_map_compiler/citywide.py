from __future__ import annotations

import hashlib
import heapq
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .crs import to_project_xy
from .fixture import compile_normalized_snapshot, load_snapshot, normalize_snapshot
from .model import Directionality, RoadCenterline, RoadSurface
from .tiling import feature_tile_counts
from .vertical import ElevationSampler, VerticalResolver, road_level_endpoints, road_structure_kind

REQUIRED_BOROUGHS = ("Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island")
ENDPOINT_SNAP_TOLERANCE_M = 0.75
DEFAULT_ROUTE_SNAP_MAX_M = 250.0


@dataclass(frozen=True, slots=True)
class RouteAuditSpec:
    name: str
    waypoints_wgs84: tuple[tuple[float, float], ...]
    required_boroughs: tuple[str, ...] = ()
    max_snap_m: float = DEFAULT_ROUTE_SNAP_MAX_M


DEFAULT_ROUTE_AUDITS = (
    RouteAuditSpec(
        "brooklyn-bridge",
        ((-74.0050, 40.7113), (-73.9902, 40.6997)),
        ("Manhattan", "Brooklyn"),
    ),
    RouteAuditSpec(
        "queensboro-bridge",
        ((-73.9641, 40.7588), (-73.9440, 40.7552)),
        ("Manhattan", "Queens"),
    ),
    RouteAuditSpec(
        "macombs-dam-bridge",
        ((-73.9360, 40.8275), (-73.9281, 40.8315)),
        ("Manhattan", "Bronx"),
    ),
    RouteAuditSpec(
        "bronx-whitestone-bridge",
        ((-73.8375, 40.7919), (-73.8342, 40.8175)),
        ("Queens", "Bronx"),
    ),
    RouteAuditSpec(
        "verrazzano-narrows-bridge",
        ((-74.0269, 40.6088), (-74.0580, 40.6062)),
        ("Brooklyn", "Staten Island"),
    ),
)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    stable_id: str
    source_id: str
    borough: str | None
    start_node: int
    end_node: int
    length_m: float
    directionality: Directionality
    structure_kind: str


@dataclass(slots=True)
class RoadGraph:
    node_xy: dict[int, tuple[float, float]]
    edges: list[GraphEdge]
    undirected: dict[int, list[tuple[int, int]]]
    directed: dict[int, list[tuple[int, int]]]
    incident_boroughs: dict[int, set[str]]


class _DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value: int) -> int:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


def _stable_id(road: RoadCenterline) -> str:
    return f"{road.provenance.source_key}:{road.source_id}"


def _path_length(path) -> float:
    return sum(
        math.hypot(second.x - first.x, second.y - first.y)
        for first, second in zip(path, path[1:])
    )


def build_road_graph(
    roads: Iterable[RoadCenterline],
    *,
    snap_tolerance_m: float = ENDPOINT_SNAP_TOLERANCE_M,
) -> RoadGraph:
    if snap_tolerance_m <= 0:
        raise ValueError("snap_tolerance_m must be positive")

    roads = list(roads)
    endpoint_records: list[tuple[float, float, int, int, int]] = []
    path_records: list[tuple[RoadCenterline, int, int, float, str]] = []

    for road in roads:
        from_level, to_level, _ = road_level_endpoints(road)
        structure_kind = road_structure_kind(road, from_level, to_level)
        for path in road.paths:
            if len(path) < 2:
                continue
            start_index = len(endpoint_records)
            endpoint_records.append((path[0].x, path[0].y, from_level, len(path_records), 0))
            end_index = len(endpoint_records)
            endpoint_records.append((path[-1].x, path[-1].y, to_level, len(path_records), 1))
            path_records.append((road, start_index, end_index, _path_length(path), structure_kind))

    dsu = _DisjointSet(len(endpoint_records))
    grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    cell_size = snap_tolerance_m
    for index, (x, y, level, _, _) in enumerate(endpoint_records):
        cell_x = math.floor(x / cell_size)
        cell_y = math.floor(y / cell_size)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in grid.get((cell_x + dx, cell_y + dy, level), ()):
                    ox, oy, _, _, _ = endpoint_records[other]
                    if math.hypot(x - ox, y - oy) <= snap_tolerance_m:
                        dsu.union(index, other)
        grid[(cell_x, cell_y, level)].append(index)

    members: dict[int, list[int]] = defaultdict(list)
    for index in range(len(endpoint_records)):
        members[dsu.find(index)].append(index)
    ordered_roots = sorted(members, key=lambda root: min(members[root]))
    root_to_node = {root: node for node, root in enumerate(ordered_roots)}

    node_xy: dict[int, tuple[float, float]] = {}
    for root, node in root_to_node.items():
        xs = [endpoint_records[index][0] for index in members[root]]
        ys = [endpoint_records[index][1] for index in members[root]]
        node_xy[node] = (sum(xs) / len(xs), sum(ys) / len(ys))

    edges: list[GraphEdge] = []
    undirected: dict[int, list[tuple[int, int]]] = defaultdict(list)
    directed: dict[int, list[tuple[int, int]]] = defaultdict(list)
    incident_boroughs: dict[int, set[str]] = defaultdict(set)

    for road, start_endpoint, end_endpoint, length_m, structure_kind in path_records:
        start_node = root_to_node[dsu.find(start_endpoint)]
        end_node = root_to_node[dsu.find(end_endpoint)]
        edge = GraphEdge(
            stable_id=_stable_id(road),
            source_id=road.source_id,
            borough=road.borough,
            start_node=start_node,
            end_node=end_node,
            length_m=length_m,
            directionality=road.semantics.directionality,
            structure_kind=structure_kind,
        )
        edge_index = len(edges)
        edges.append(edge)
        undirected[start_node].append((end_node, edge_index))
        undirected[end_node].append((start_node, edge_index))
        if edge.directionality is not Directionality.REVERSE:
            directed[start_node].append((end_node, edge_index))
        if edge.directionality is not Directionality.FORWARD:
            directed[end_node].append((start_node, edge_index))
        if road.borough:
            incident_boroughs[start_node].add(road.borough)
            incident_boroughs[end_node].add(road.borough)

    return RoadGraph(
        node_xy=node_xy,
        edges=edges,
        undirected=dict(undirected),
        directed=dict(directed),
        incident_boroughs=dict(incident_boroughs),
    )


def _component_nodes(graph: RoadGraph) -> list[set[int]]:
    remaining = set(graph.node_xy)
    components: list[set[int]] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        component: set[int] = set()
        remaining.remove(start)
        while stack:
            node = stack.pop()
            component.add(node)
            for neighbor, _ in graph.undirected.get(node, ()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
        components.append(component)
    return components


def _nearest_node(graph: RoadGraph, lon: float, lat: float) -> tuple[int | None, float | None]:
    if not graph.node_xy:
        return None, None
    x, y = to_project_xy(lon, lat, "EPSG:4326")
    best_node = None
    best_distance = math.inf
    for node, (nx, ny) in graph.node_xy.items():
        distance = math.hypot(nx - x, ny - y)
        if distance < best_distance:
            best_node = node
            best_distance = distance
    return best_node, best_distance


def _shortest_path(
    graph: RoadGraph,
    start: int,
    end: int,
    *,
    directed: bool,
) -> tuple[float | None, list[int]]:
    if start == end:
        return 0.0, []
    adjacency = graph.directed if directed else graph.undirected
    distances = {start: 0.0}
    previous: dict[int, tuple[int, int]] = {}
    queue: list[tuple[float, int]] = [(0.0, start)]

    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances.get(node):
            continue
        if node == end:
            break
        for neighbor, edge_index in adjacency.get(node, ()):
            candidate = distance + graph.edges[edge_index].length_m
            if candidate + 1e-9 >= distances.get(neighbor, math.inf):
                continue
            distances[neighbor] = candidate
            previous[neighbor] = (node, edge_index)
            heapq.heappush(queue, (candidate, neighbor))

    if end not in distances:
        return None, []

    edge_path: list[int] = []
    node = end
    while node != start:
        previous_node, edge_index = previous[node]
        edge_path.append(edge_index)
        node = previous_node
    edge_path.reverse()
    return distances[end], edge_path


def audit_route(graph: RoadGraph, spec: RouteAuditSpec) -> dict[str, Any]:
    if len(spec.waypoints_wgs84) < 2:
        raise ValueError(f"route {spec.name} requires at least two waypoints")

    snapped_nodes: list[int] = []
    snaps: list[dict[str, Any]] = []
    for lon, lat in spec.waypoints_wgs84:
        node, distance_m = _nearest_node(graph, lon, lat)
        snap_ok = node is not None and distance_m is not None and distance_m <= spec.max_snap_m
        snaps.append(
            {
                "wgs84": [lon, lat],
                "node": node,
                "distance_m": round(distance_m, 3) if distance_m is not None else None,
                "within_limit": snap_ok,
            }
        )
        if node is None:
            continue
        snapped_nodes.append(node)

    if len(snapped_nodes) != len(spec.waypoints_wgs84) or not all(snap["within_limit"] for snap in snaps):
        return {
            "name": spec.name,
            "connected": False,
            "directionally_connected": False,
            "distance_m": None,
            "required_boroughs": list(spec.required_boroughs),
            "path_boroughs": [],
            "snaps": snaps,
            "failure": "waypoint-snap",
        }

    undirected_distance = 0.0
    directed_distance = 0.0
    path_edge_indices: list[int] = []
    directional_ok = True
    for start, end in zip(snapped_nodes, snapped_nodes[1:]):
        distance, edges = _shortest_path(graph, start, end, directed=False)
        if distance is None:
            return {
                "name": spec.name,
                "connected": False,
                "directionally_connected": False,
                "distance_m": None,
                "required_boroughs": list(spec.required_boroughs),
                "path_boroughs": [],
                "snaps": snaps,
                "failure": "disconnected",
            }
        undirected_distance += distance
        path_edge_indices.extend(edges)
        directed_segment_distance, _ = _shortest_path(graph, start, end, directed=True)
        if directed_segment_distance is None:
            directional_ok = False
        else:
            directed_distance += directed_segment_distance

    path_boroughs = sorted(
        {
            graph.edges[index].borough
            for index in path_edge_indices
            if graph.edges[index].borough is not None
        }
    )
    required_present = set(spec.required_boroughs).issubset(path_boroughs)
    connected = required_present
    return {
        "name": spec.name,
        "connected": connected,
        "directionally_connected": connected and directional_ok,
        "distance_m": round(undirected_distance, 3),
        "directed_distance_m": round(directed_distance, 3) if directional_ok else None,
        "required_boroughs": list(spec.required_boroughs),
        "path_boroughs": path_boroughs,
        "snaps": snaps,
        "failure": None if connected else "required-boroughs-not-on-path",
    }


def _duplicate_road_ids(roads: Sequence[RoadCenterline]) -> list[str]:
    counts = Counter(_stable_id(road) for road in roads)
    return sorted(stable_id for stable_id, count in counts.items() if count > 1)


def _invalid_road_ids(roads: Sequence[RoadCenterline]) -> list[str]:
    invalid = []
    for road in roads:
        if not road.paths or any(
            len(path) < 2
            or _path_length(path) <= 1e-6
            or any(not (math.isfinite(point.x) and math.isfinite(point.y)) for point in path)
            for path in road.paths
        ):
            invalid.append(_stable_id(road))
    return sorted(invalid)


def audit_citywide(
    roads: Sequence[RoadCenterline],
    surfaces: Sequence[RoadSurface],
    tiles: Mapping[str, Mapping[str, Any]],
    *,
    vertical: VerticalResolver | None = None,
    route_audits: Sequence[RouteAuditSpec] = DEFAULT_ROUTE_AUDITS,
) -> dict[str, Any]:
    graph = build_road_graph(roads)
    borough_counts = Counter(road.borough for road in roads if road.borough)
    missing_boroughs = [borough for borough in REQUIRED_BOROUGHS if borough_counts[borough] == 0]

    components = _component_nodes(graph)
    component_edge_counts: list[tuple[int, set[int]]] = []
    for component in components:
        edge_indexes = {
            edge_index
            for node in component
            for _, edge_index in graph.undirected.get(node, ())
        }
        component_edge_counts.append((len(edge_indexes), component))
    component_edge_counts.sort(key=lambda item: (-item[0], min(item[1]) if item[1] else -1))
    main_nodes = component_edge_counts[0][1] if component_edge_counts else set()
    disconnected_ids = sorted(
        {
            edge.stable_id
            for edge in graph.edges
            if edge.start_node not in main_nodes or edge.end_node not in main_nodes
        }
    )

    cross_borough_pairs: Counter[str] = Counter()
    cross_borough_node_count = 0
    for boroughs in graph.incident_boroughs.values():
        if len(boroughs) < 2:
            continue
        cross_borough_node_count += 1
        for left, right in combinations(sorted(boroughs), 2):
            cross_borough_pairs[f"{left}|{right}"] += 1

    structure_counts = Counter(edge.structure_kind for edge in graph.edges)
    road_tile_counts = feature_tile_counts(dict(tiles), "roads")
    cross_tile_road_count = sum(1 for count in road_tile_counts.values() if count > 1)

    vertical_diagnostics = vertical.diagnostics_payload() if vertical is not None else []
    vertical_code_counts = Counter(item["code"] for item in vertical_diagnostics)
    unresolved_surfaces = 0
    if vertical is not None:
        unresolved_surfaces = sum(
            1
            for surface in surfaces
            if vertical.surface_association(surface).status != "resolved"
        )

    route_results = [audit_route(graph, spec) for spec in route_audits]
    duplicate_ids = _duplicate_road_ids(roads)
    invalid_ids = _invalid_road_ids(roads)
    total_edges = len(graph.edges)
    main_edge_count = component_edge_counts[0][0] if component_edge_counts else 0

    return {
        "schema_version": 1,
        "borough_coverage": {
            "required": list(REQUIRED_BOROUGHS),
            "road_counts": {borough: borough_counts[borough] for borough in REQUIRED_BOROUGHS},
            "missing": missing_boroughs,
        },
        "topology": {
            "node_count": len(graph.node_xy),
            "edge_count": total_edges,
            "component_count": len(components),
            "largest_component_edge_count": main_edge_count,
            "largest_component_edge_fraction": (
                round(main_edge_count / total_edges, 6) if total_edges else 0.0
            ),
            "disconnected_road_count": len(disconnected_ids),
            "disconnected_road_sample": disconnected_ids[:100],
            "cross_borough_node_count": cross_borough_node_count,
            "cross_borough_pairs": dict(sorted(cross_borough_pairs.items())),
            "cross_tile_road_count": cross_tile_road_count,
            "structure_counts": dict(sorted(structure_counts.items())),
        },
        "invalid_topology": {
            "duplicate_road_id_count": len(duplicate_ids),
            "duplicate_road_id_sample": duplicate_ids[:100],
            "invalid_road_count": len(invalid_ids),
            "invalid_road_sample": invalid_ids[:100],
        },
        "vertical": {
            "enabled": vertical is not None,
            "unresolved_surface_count": unresolved_surfaces,
            "diagnostic_counts": dict(sorted(vertical_code_counts.items())),
        },
        "routes": route_results,
    }


def compile_citywide_snapshot(
    snapshot: Mapping[str, Any],
    *,
    elevation_sampler: ElevationSampler,
    route_audits: Sequence[RouteAuditSpec] = DEFAULT_ROUTE_AUDITS,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    surfaces, roads = normalize_snapshot(snapshot)
    manifest, tiles, vertical = compile_normalized_snapshot(
        snapshot,
        surfaces,
        roads,
        elevation_sampler=elevation_sampler,
        return_vertical=True,
    )
    assert vertical is not None
    manifest["scope"] = "nyc-five-boroughs"
    manifest["boroughs"] = list(REQUIRED_BOROUGHS)
    manifest["citywide_audit"] = audit_citywide(
        roads,
        surfaces,
        tiles,
        vertical=vertical,
        route_audits=route_audits,
    )
    return manifest, tiles


def _tile_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_compiled_citywide(
    snapshot_path: Path,
    output_dir: Path,
    *,
    elevation_sampler: ElevationSampler,
    route_audits: Sequence[RouteAuditSpec] = DEFAULT_ROUTE_AUDITS,
) -> dict[str, Any]:
    manifest, tiles = compile_citywide_snapshot(
        load_snapshot(snapshot_path),
        elevation_sampler=elevation_sampler,
        route_audits=route_audits,
    )
    tiles_dir = output_dir / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)

    expected_files = set()
    for entry in manifest["tiles"]:
        payload = tiles[entry["tile_id"]]
        raw = _tile_bytes(payload)
        target = output_dir / entry["file"]
        expected_files.add(target.resolve())
        target.write_bytes(raw)
        entry["sha256"] = hashlib.sha256(raw).hexdigest()
        entry["bytes"] = len(raw)

    for stale in tiles_dir.glob("*.json"):
        if stale.resolve() not in expected_files:
            stale.unlink()

    audit = manifest["citywide_audit"]
    audit["output_validation"] = {
        "expected_tile_files": len(expected_files),
        "missing_tile_files": [
            entry["file"]
            for entry in manifest["tiles"]
            if not (output_dir / entry["file"]).is_file()
        ],
    }
    (output_dir / "citywide_audit.json").write_text(
        json.dumps(audit, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
