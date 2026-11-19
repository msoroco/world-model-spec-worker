"""Same-site straight-route construction for the C125751 turn comparison.

The straight exit is an independently sourced route. This module checks the
controlled difference before any Native actor is spawned. Angle bounds are
engineering route checks, not legal definitions of a turn.
"""

from contextlib import contextmanager
import copy
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import Point, Polygon

from route_control import steering_command
from yield_controller import apply_speed_control


FIXED_SITE_FIELDS = (
    "native_map_name", "native_junction_id", "crossing_polygon_xy_m",
    "crossing_polygon_source", "approach_headings_deg",
    "expected_approach_lanes", "approach_geometry_source",
    "governed_signal_ids", "device_inventory_source",
    "selected_stop_references", "cameras",
)
ROLES = ("ego", "other")
COMPARATOR_CASE = "testing__C125751__NRS-484B-250-2__motor_vehicle_driver__opposite_straight_comparator"


def verify_route_source(reference):
    """Read the retained original route document before building a comparator."""
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise ValueError("Original straight-route source path and hash required")
    path = Path(reference["path"])
    digest = reference["sha256"]
    if (not path.is_file() or not isinstance(digest, str) or len(digest) != 64 or
            hashlib.sha256(path.read_bytes()).hexdigest() != digest):
        raise ValueError("Straight-route source missing or changed")
    source = json.loads(path.read_text())
    if (source.get("format") != "worker-c125751-straight-route-source-v1" or
            source.get("case_id") != COMPARATOR_CASE or
            source.get("site_baseline") != "opposite_left_turn" or
            source.get("route_role") != "ego" or
            type(source.get("diagnostic_only")) is not bool or
            not source.get("source_basis")):
        raise ValueError("Exact source identity for straight comparator required")
    return source


def _bearing(start, end):
    if (not isinstance(start, list) or not isinstance(end, list) or
            len(start) != 2 or len(end) != 2 or
            any(type(value) not in (int, float) or not math.isfinite(value)
                for value in start + end)):
        raise ValueError("Finite sourced XY route points required")
    dx, dy = end[0] - start[0], end[1] - start[1]
    if math.hypot(dx, dy) < .1:
        raise ValueError("Distinct sourced route points required")
    return math.degrees(math.atan2(dy, dx))


def _angle(start, end):
    return (end - start + 180) % 360 - 180


def straight_site(left_site, straight_ego_route, route_source):
    """Keep all source site facts except ego's exit route fixed.

    The other driver's route and both approach points remain byte-equivalent
    JSON values. A caller must retain the straight route's original map source.
    """
    source = verify_route_source(route_source)
    if straight_ego_route != source.get("route_xy_m"):
        raise ValueError("Straight route differs from retained original source")
    if not isinstance(left_site, dict) or any(key not in left_site for key in FIXED_SITE_FIELDS):
        raise ValueError("Complete reviewed left-turn site required")
    old_routes = left_site.get("routes")
    if not isinstance(old_routes, dict) or set(old_routes) != set(ROLES):
        raise ValueError("Two reviewed original routes required")
    old_ego = old_routes["ego"]
    if (not isinstance(old_ego, list) or len(old_ego) < 4 or
            not isinstance(straight_ego_route, list) or len(straight_ego_route) < 4 or
            straight_ego_route[:3] != old_ego[:3] or
            straight_ego_route == old_ego):
        raise ValueError("Straight comparator must retain ego approach and change exit")
    polygon = Polygon(left_site["crossing_polygon_xy_m"])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Valid same-site crossing polygon required")
    for label, route in (("left", old_ego), ("straight", straight_ego_route),
                         ("opposing", old_routes["other"])):
        if not isinstance(route, list) or len(route) < 4:
            raise ValueError("Complete " + label + " route required")
        for point in route:
            if (not isinstance(point, list) or len(point) != 2 or
                    any(type(value) not in (int, float) or not math.isfinite(value)
                        for value in point)):
                raise ValueError("Finite " + label + " route point required")
            _bearing(point, [point[0] + 1, point[1]])
        if (polygon.covers(Point(route[0])) or
                not polygon.contains(Point(route[2])) or
                polygon.covers(Point(route[-1]))):
            raise ValueError(label + " route must enter and leave same crossing")
    left = _angle(_bearing(old_ego[0], old_ego[1]),
                  _bearing(old_ego[-2], old_ego[-1]))
    straight = _angle(_bearing(straight_ego_route[0], straight_ego_route[1]),
                      _bearing(straight_ego_route[-2], straight_ego_route[-1]))
    opposing = abs(_angle(_bearing(old_ego[0], old_ego[1]),
                           _bearing(old_routes["other"][0], old_routes["other"][1])))
    if not 45 <= left <= 135 or abs(straight) > 30 or abs(opposing - 180) > 20:
        raise ValueError("Left/straight controlled route geometry differs")
    comparator = copy.deepcopy(left_site)
    comparator["routes"]["ego"] = copy.deepcopy(straight_ego_route)
    if any(comparator[key] != left_site[key] for key in FIXED_SITE_FIELDS):
        raise ValueError("Controlled site field changed")
    return {"site": comparator, "baseline_site": copy.deepcopy(left_site),
            "straight_route_source": route_source,
            "left_deflection_deg": left, "straight_deflection_deg": straight,
            "approach_separation_deg": opposing,
            "physical_or_legal_acceptance_claimed": False}


def compare_sites(left_site, candidate_site, route_source):
    """Reject any undeclared site, opposing route or approach change."""
    source = verify_route_source(route_source)
    expected = straight_site(left_site, source["route_xy_m"], route_source)["site"]
    if candidate_site != expected:
        raise ValueError("Straight comparator changes a fixed site field or route")
    return {"fixed_fields": list(FIXED_SITE_FIELDS),
            "deliberate_difference": "ego exit route: left to straight",
            "straight_route_source_sha256": route_source["sha256"],
            "physical_or_legal_acceptance_claimed": False}


@contextmanager
def construct_straight_pair(world, blueprints, transforms, plan):
    """Spawn the same two approach lanes after checking the straight plan."""
    compare_sites(plan["baseline_site"], plan["site"],
                  plan["straight_route_source"])
    site = plan["site"]
    if set(blueprints) != set(ROLES) or set(transforms) != set(ROLES):
        raise ValueError("Both reviewed Native blueprints and transforms required")
    lanes = site["expected_approach_lanes"]
    if not isinstance(lanes, dict) or set(lanes) != set(ROLES) or lanes["ego"] == lanes["other"]:
        raise ValueError("Two distinct same-site approach lanes required")
    actors = {}
    try:
        for role in ROLES:
            actor = world.try_spawn_actor(blueprints[role], transforms[role])
            if actor is None:
                raise ValueError("Native actor spawn failed: " + role)
            actors[role] = actor
        world.tick()
        for role, actor in actors.items():
            waypoint = world.get_map().get_waypoint(actor.get_location(), project_to_road=False)
            if waypoint is None or [waypoint.road_id, waypoint.lane_id] != lanes[role]:
                raise ValueError("Native actor outside same-site approach lane: " + role)
            yaw = float(actor.get_transform().rotation.yaw)
            route = site["routes"][role]
            if not math.isfinite(yaw) or abs(_angle(_bearing(route[0], route[1]), yaw)) > 20:
                raise ValueError("Native actor faces away from sourced approach: " + role)
        yield actors
    finally:
        for actor in reversed(list(actors.values())):
            actor.destroy()


def command_straight_pair(carla, actors, plan, progress, frame_index,
                          release_frames, target_speeds_mps, lookahead_m=5.0):
    """Issue two route commands using the unchanged candidate timing controls."""
    compare_sites(plan["baseline_site"], plan["site"],
                  plan["straight_route_source"])
    if (set(actors) != set(ROLES) or set(progress) != set(ROLES) or
            set(release_frames) != set(ROLES) or
            set(target_speeds_mps) != set(ROLES) or
            type(frame_index) is not int or frame_index < 0 or
            any(type(release_frames[r]) is not int or release_frames[r] < 1 for r in ROLES) or
            any(type(target_speeds_mps[r]) not in (int, float) or
                not math.isfinite(target_speeds_mps[r]) or target_speeds_mps[r] <= 0
                for r in ROLES)):
        raise ValueError("Complete paired straight candidate controls required")
    decisions = {}
    for role in ROLES:
        pose = actors[role].get_transform()
        steer, next_index = steering_command(
            float(pose.location.x), float(pose.location.y), float(pose.rotation.yaw),
            plan["site"]["routes"][role], progress[role], lookahead_m)
        decisions[role] = {"steer": steer, "next_index": next_index,
                           "release_allowed": frame_index >= release_frames[role]}
    for role in ROLES:
        decision = decisions[role]
        decision["applied_control"] = apply_speed_control(
            carla, actors[role], float(target_speeds_mps[role]),
            not decision["release_allowed"], decision["steer"])
        progress[role] = decision["next_index"]
    return {"frame_index": frame_index, "decisions": decisions,
            "physical_or_legal_acceptance_claimed": False}
