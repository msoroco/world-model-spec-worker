"""Source-gated Native T-junction construction with separate purpose and route facts."""

import hashlib
import json
import math
from pathlib import Path

from package_spec import AID


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite numeric source value required")
    return float(value)


def sealed_json(path, expected_sha256):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("source sha256 mismatch")
    return json.loads(raw)


def construct(site, case):
    if site.get("assignment_id") != AID or site.get("case_id") != case:
        raise ValueError("exact case/site identity differs")
    if site.get("source_kind") != "original_native_map_geometry" or site.get("reviewed_original_native_site") is not True:
        raise ValueError("reviewed original Native T-junction source required")
    for key in ("source_id", "map_name", "map_sha256", "highway_source", "turn_lane_source", "connected_route_source", "driver_actor_id"):
        if not site.get(key):
            raise ValueError("missing source-backed Native T-junction fact: " + key)
    if site.get("public_highway") is not True or site.get("one_right_turn_lane") is not True or site.get("exclusive_right_turn") is not True:
        raise ValueError("public highway with one exclusive right-turn lane required")
    ids = site.get("native_ids")
    if not isinstance(ids, dict) or not all(ids.get(key) for key in ("entry_road", "turn_lane", "right_exit_road", "t_junction")):
        raise ValueError("source-surveyed Native road, lane and junction IDs required")
    if ids["entry_road"] == ids["right_exit_road"]:
        raise ValueError("distinct connected right exit required")
    routes = site.get("connected_routes")
    if not isinstance(routes, dict) or routes.get("right_turn") != [ids["entry_road"], ids["right_exit_road"]]:
        raise ValueError("source-confirmed connected right turn required")
    plan = {"right_turn_purpose": ("right_turn", "right_turn"),
            "through_purpose": ("through", "right_turn"),
            "left_turn_purpose": ("left_turn", "right_turn"),
            "right_turn_route_mismatch": ("right_turn", "other")}
    suffix = case.removeprefix(AID + "__")
    if suffix not in plan:
        raise ValueError("unsupported exact right-turn-lane case")
    purpose, route = plan[suffix]
    declaration = site.get("purpose_declaration")
    if not isinstance(declaration, dict) or declaration.get("declared_purpose") != purpose or not declaration.get("source_ref"):
        raise ValueError("independent exact declared purpose required")
    if type(declaration.get("declared_before_frame")) is not int or declaration["declared_before_frame"] >= 0:
        raise ValueError("purpose must be sourced before initial lane entry")
    if site.get("requested_departure_route") != route:
        raise ValueError("departure route request differs from exact case")
    if route == "other":
        other = site.get("alternate_exit")
        if not isinstance(other, dict) or not other.get("source") or not other.get("road_id") or other["road_id"] == ids["right_exit_road"]:
            raise ValueError("connected alternate exit for route mismatch required")
    spawn = site.get("native_spawn")
    if not isinstance(spawn, dict) or not spawn.get("source_id") or not spawn.get("blueprint_id") or not isinstance(spawn.get("pose_xyz_ypr"), list) or len(spawn["pose_xyz_ypr"]) != 6:
        raise ValueError("source-backed vehicle blueprint and pose required")
    for value in spawn["pose_xyz_ypr"]:
        number(value)
    trajectory = site.get("trajectory")
    if not isinstance(trajectory, dict) or not trajectory.get("source_id") or not isinstance(trajectory.get(route), list) or len(trajectory[route]) < 3:
        raise ValueError("source-backed connected route trajectory required")
    for point in trajectory[route]:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("route point needs world x/y")
        for value in point:
            number(value)
    return {"case_id": case, "declared_purpose": purpose, "departure_route": route,
            "trajectory_xy": trajectory[route], "native_ids": ids,
            "purpose_declaration": declaration, "native_readback_required": True}
