"""Source-sealed topology and route gate for NRS 484B.223(3)(b).

A map lane label is not proof of a legally designated shared turn lane. The
reviewed highway/design packet and original OpenDRIVE bytes are both required.
"""
from __future__ import annotations

import hashlib
import json
from math import hypot, isfinite
from pathlib import Path


def _read(root: Path, binding: dict) -> bytes:
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        raise ValueError("exact source binding required")
    relative = Path(binding["path"])
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("source path outside attempt")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
        raise ValueError("reviewed source missing")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != binding["sha256"]:
        raise ValueError("reviewed source hash mismatch")
    return data


def _direction(points: list) -> tuple[float, float]:
    if len(points) < 2 or any(len(p) != 2 for p in points):
        raise ValueError("original lane centreline missing")
    a, b = points[0], points[-1]
    values = [float(v) for v in (*a, *b)]
    if not all(isfinite(v) for v in values):
        raise ValueError("nonfinite original lane centreline")
    x, y = values[2] - values[0], values[3] - values[1]
    length = hypot(x, y)
    if length < 10:
        raise ValueError("lane direction not established")
    return x / length, y / length


def inspect_site(packet: dict, case_kind: str) -> dict:
    if case_kind not in {"short_travel", "boundary_travel", "long_travel",
                         "onto_highway_contrast"}:
        raise ValueError("unknown exact case kind")
    if not packet.get("native_map_source") or not packet.get("highway_review_source"):
        raise ValueError("Native map and reviewed highway sources required")
    if packet.get("public_highway_confirmed") is not True:
        raise ValueError("highway status unverified")
    if (not packet.get("ego_id") or not packet.get("driver_id") or
            packet["ego_id"] != packet["driver_id"]):
        raise ValueError("reviewed ego and original driver identity differ")
    lanes = packet.get("lanes")
    if not isinstance(lanes, list) or len(lanes) < 3:
        raise ValueError("original lane inventory missing")
    ids = [lane.get("id") for lane in lanes]
    if any(not lane for lane in ids) or len(set(ids)) != len(ids):
        raise ValueError("original lane identifiers missing or duplicated")
    shared = [lane for lane in lanes if lane.get("center_turn_lane") is True]
    if len(shared) != 1:
        raise ValueError("exactly one shared center turn lane required")
    center = shared[0]
    if (center.get("exclusive_turn_use") is not True or
            set(center.get("permitted_turn_directions", [])) != {"negative", "positive"}):
        raise ValueError("bidirectional exclusive turning design unverified")
    road = center.get("road_id")
    through = [lane for lane in lanes if lane.get("highway_through") is True]
    if not road or len(through) != 2 or any(lane.get("road_id") != road for lane in through):
        raise ValueError("two highway through directions required")
    a, b = (_direction(lane["centreline_xy_m"]) for lane in through)
    if a[0] * b[0] + a[1] * b[1] > -.8:
        raise ValueError("highway through directions are not opposing")
    junction = packet.get("junction")
    if not isinstance(junction, dict) or not junction.get("id"):
        raise ValueError("source-bound junction missing")
    if junction.get("kind") not in {"street_intersection", "alley"}:
        raise ValueError("junction classification missing")
    if junction["kind"] != "street_intersection":
        raise ValueError("exact case requires reviewed street intersection")
    route = packet.get("route")
    if not isinstance(route, dict) or route.get("center_lane_id") != center["id"]:
        raise ValueError("route does not enter governed center lane")
    if not isinstance(route.get("waypoints_xy_m"), list) or len(route["waypoints_xy_m"]) < 3:
        raise ValueError("source-bound route geometry missing")
    for point in route["waypoints_xy_m"]:
        if len(point) != 2 or not all(isfinite(float(v)) for v in point):
            raise ValueError("route waypoint invalid")
    mode = route.get("relationship")
    expected = "onto_highway" if case_kind == "onto_highway_contrast" else "from_highway"
    if mode != expected:
        raise ValueError("route highway relationship differs from exact case")
    if route.get("approach_road_id") == route.get("departure_road_id"):
        raise ValueError("left turn route lacks distinct road identity")
    if mode == "from_highway" and route.get("approach_road_id") != road:
        raise ValueError("from-highway approach road mismatch")
    if mode == "onto_highway" and route.get("departure_road_id") != road:
        raise ValueError("onto-highway departure road mismatch")
    return {"center_lane_id": center["id"], "highway_road_id": road,
            "junction_kind": junction["kind"], "route_relationship": mode,
            "through_lane_ids": [lane["id"] for lane in through]}


def verify_reviewed_site(attempt_root, packet: dict, case_kind: str, live_opendrive: str) -> dict:
    root = Path(attempt_root).resolve()
    map_record = json.loads(_read(root, packet["native_map_source"]))
    review = json.loads(_read(root, packet["highway_review_source"]))
    if map_record.get("opendrive_sha256") != hashlib.sha256(live_opendrive.encode()).hexdigest():
        raise ValueError("live OpenDRIVE differs from reviewed map")
    if (review.get("public_highway_confirmed") is not True or
            review.get("single_bidirectional_turn_only_center_lane") is not True or
            review.get("highway_road_id") != packet.get("highway_road_id")):
        raise ValueError("highway and lane design review not established")
    topology = inspect_site(packet, case_kind)
    if topology["highway_road_id"] != review["highway_road_id"]:
        raise ValueError("reviewed highway road differs from Native topology")
    center = next(lane for lane in packet["lanes"] if lane["id"] == topology["center_lane_id"])
    polygon = center.get("polygon_xy_m")
    if (not isinstance(polygon, list) or len(polygon) < 4 or
            review.get("center_lane_polygon_xy_m") != polygon):
        raise ValueError("reviewed original center-lane polygon missing or changed")
    topology["center_lane_polygon_xy_m"] = polygon
    return topology
