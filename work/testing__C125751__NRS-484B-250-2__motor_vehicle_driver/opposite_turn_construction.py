"""Construct the opposite-approach left-turn exception candidate lazily.

The caller supplies a source-reviewed Native site, route points, transforms and
blueprints. Angular bounds are construction checks, not statutory definitions.
"""

from contextlib import contextmanager
import math
from shapely.geometry import Point, Polygon

from route_control import steering_command
from yield_controller import apply_speed_control


FALLBACK_RISKS = {
    "fallback1": ("spawn_occupied", "transforms"),
    "fallback2": ("entry_timing_missed", "target_speeds_mps"),
    "fallback3": ("turn_path_missed", "lookahead_m"),
}

TRIGGER_SOURCES = {
    "fallback1": ("spawn_attempt.json", "approach_spawn_succeeded"),
    "fallback2": ("crossing_history.jsonl", "paired_body_entry_observed_by_planned_frame"),
    "fallback3": ("body_history.jsonl", "turning_body_route_deviation_m"),
}


def validate_opposite_fallbacks(primary, fallbacks, turning_role):
    """Validate three predeclared, source-reviewed engineering alternatives.

    These are alternate attempts for the same case. Trigger thresholds are
    engineering observations and never statutory priority or legal cutoffs.
    """
    fields = {"site", "transforms", "release_frames", "target_speeds_mps", "frames", "lookahead_m"}
    if not isinstance(primary, dict) or set(primary) != fields:
        raise ValueError("Complete primary opposite-turn construction required")
    if not isinstance(fallbacks, dict) or set(fallbacks) != set(FALLBACK_RISKS):
        raise ValueError("Three distinct opposite-turn fallbacks required")
    site = primary["site"]
    if not isinstance(site, dict):
        raise ValueError("Sourced primary site required")
    check_routes(site.get("routes"), turning_role, site.get("crossing_polygon_xy_m"))
    if type(primary["frames"]) is not int or not 2 <= primary["frames"] <= 1100:
        raise ValueError("Bounded primary frame count required")
    if (type(primary["lookahead_m"]) not in (int, float) or
            not math.isfinite(primary["lookahead_m"]) or primary["lookahead_m"] <= 0):
        raise ValueError("Finite positive primary route lookahead required")
    if not isinstance(primary["transforms"], dict) or set(primary["transforms"]) != {"ego", "other"}:
        raise ValueError("Two primary spawn transforms required")
    if (not isinstance(primary["release_frames"], dict) or
            set(primary["release_frames"]) != {"ego", "other"} or
            any(type(value) is not int or not 1 <= value < primary["frames"]
                for value in primary["release_frames"].values())):
        raise ValueError("Bounded primary release schedule required")
    if (not isinstance(primary["target_speeds_mps"], dict) or
            set(primary["target_speeds_mps"]) != {"ego", "other"} or
            any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                for value in primary["target_speeds_mps"].values())):
        raise ValueError("Finite positive primary target speeds required")
    camera_names = {"overview", "approach", "reference_corner", "driver_reference"}
    if not isinstance(site.get("cameras"), dict) or set(site["cameras"]) != camera_names:
        raise ValueError("Four primary source cameras required")
    accepted = {}
    for name, (risk, changed) in FALLBACK_RISKS.items():
        item = fallbacks[name]
        trigger = item.get("trigger_measurement") if isinstance(item, dict) else None
        if (not isinstance(item, dict) or
                set(item) != fields | {"physical_risk_trigger", "trigger_measurement", "source_review"} or
                item["physical_risk_trigger"] != risk or
                not isinstance(trigger, dict) or set(trigger) != {"source", "metric", "failure_condition"} or
                (trigger["source"], trigger["metric"]) != TRIGGER_SOURCES[name] or
                not isinstance(trigger["failure_condition"], str) or
                not trigger["failure_condition"].strip() or
                not isinstance(item["source_review"], str) or not item["source_review"].strip()):
            raise ValueError("Predeclared sourced physical-risk trigger required: " + name)
        if item["frames"] != primary["frames"] or item["release_frames"] != primary["release_frames"]:
            raise ValueError("Fallback changes frame count or release schedule: " + name)
        for field in fields - {changed}:
            if item[field] != primary[field]:
                raise ValueError("Fallback changes fixed construction field: " + name + ": " + field)
        if changed == "transforms":
            if (not isinstance(item["transforms"], dict) or set(item["transforms"]) != {"ego", "other"} or
                    item["transforms"] == primary["transforms"]):
                raise ValueError("Spawn fallback needs alternate paired transforms")
        elif changed == "target_speeds_mps":
            speeds = item["target_speeds_mps"]
            if (not isinstance(speeds, dict) or set(speeds) != {"ego", "other"} or
                    speeds == primary["target_speeds_mps"] or
                    any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                        for value in speeds.values())):
                raise ValueError("Timing fallback needs alternate finite target speeds")
        elif changed == "lookahead_m":
            value = item["lookahead_m"]
            if (type(value) not in (int, float) or not math.isfinite(value) or
                    value <= 0 or value == primary["lookahead_m"]):
                raise ValueError("Turn-path fallback needs alternate finite lookahead")
        accepted[name] = item
    return {"primary": primary, "fallbacks": accepted,
            "case_count_added": 0, "physical_or_legal_acceptance_claimed": False}


def _bearing(a, b):
    if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)) or len(a) != 2 or len(b) != 2:
        raise ValueError("Two sourced XY route points required")
    x, y = float(b[0]) - float(a[0]), float(b[1]) - float(a[1])
    if not all(math.isfinite(v) for v in (x, y)) or math.hypot(x, y) < .1:
        raise ValueError("Finite distinct route points required")
    return math.degrees(math.atan2(y, x))


def _angle(a, b):
    return (b - a + 180) % 360 - 180


def check_routes(routes, turning_role, crossing_polygon_xy_m=None):
    """Require two opposing entry vectors and one geometrically left exit."""
    if turning_role not in ("ego", "other") or not isinstance(routes, dict) or set(routes) != {"ego", "other"}:
        raise ValueError("Both sourced routes and a turning role required")
    measured = {}
    for role in ("ego", "other"):
        points = routes[role]
        if not isinstance(points, list) or len(points) < 4:
            raise ValueError("Approach, entry, center and exit points required: " + role)
        approach = _bearing(points[0], points[1])
        exit_bearing = _bearing(points[-2], points[-1])
        measured[role] = {"approach_bearing_deg": approach,
                          "exit_bearing_deg": exit_bearing,
                          "deflection_deg": _angle(approach, exit_bearing)}
    opposing = abs(_angle(measured["ego"]["approach_bearing_deg"],
                          measured["other"]["approach_bearing_deg"]))
    if abs(opposing - 180) > 20:
        raise ValueError("Sourced approaches are not geometrically opposite")
    if not 45 <= measured[turning_role]["deflection_deg"] <= 135:
        raise ValueError("Turning route lacks a geometric left turn")
    if crossing_polygon_xy_m is not None:
        polygon = Polygon(crossing_polygon_xy_m)
        if not polygon.is_valid or polygon.area <= 0:
            raise ValueError("Valid sourced crossing polygon required")
        for role in ("ego", "other"):
            points = routes[role]
            if (not polygon.contains(Point(points[2])) or
                    polygon.covers(Point(points[0])) or
                    polygon.covers(Point(points[-1]))):
                raise ValueError("Route does not enter and leave sourced crossing: " + role)
    return {"approach_separation_deg": opposing, "routes": measured,
            "opposite_direction_legal_judgment": "unverified",
            "left_turn_intention_legal_judgment": "unverified"}


@contextmanager
def construct_opposite_turn_pair(world, blueprints, transforms, site, turning_role):
    """Spawn both vehicles and verify their original Native approach lanes."""
    if site.get("crossing_polygon_xy_m") is None:
        raise ValueError("Sourced crossing polygon required for opposite-turn construction")
    geometry = check_routes(site.get("routes"), turning_role,
                            site.get("crossing_polygon_xy_m"))
    lanes = site.get("expected_approach_lanes")
    if not isinstance(lanes, dict) or set(lanes) != {"ego", "other"} or lanes["ego"] == lanes["other"]:
        raise ValueError("Two distinct sourced Native approach lanes required")
    if set(blueprints) != {"ego", "other"} or set(transforms) != {"ego", "other"}:
        raise ValueError("Two reviewed vehicle blueprints and transforms required")
    actors = {}
    try:
        for role in ("ego", "other"):
            actor = world.try_spawn_actor(blueprints[role], transforms[role])
            if actor is None:
                raise ValueError("Native actor spawn failed: " + role)
            actors[role] = actor
        world.tick()
        for role, actor in actors.items():
            waypoint = world.get_map().get_waypoint(actor.get_location(), project_to_road=False)
            if waypoint is None or [waypoint.road_id, waypoint.lane_id] != lanes[role]:
                raise ValueError("Native actor outside sourced approach lane: " + role)
            yaw = float(actor.get_transform().rotation.yaw)
            if not math.isfinite(yaw) or abs(_angle(geometry["routes"][role]["approach_bearing_deg"], yaw)) > 20:
                raise ValueError("Native actor faces away from sourced approach: " + role)
        yield {"actors": actors, "turning_role": turning_role, "geometry": geometry,
               "native_motion_verified": False, "legal_exception_verified": False}
    finally:
        for actor in reversed(list(actors.values())):
            actor.destroy()


def command_opposite_turn_pair(carla, actors, site, progress, frame_index,
                               release_frames, target_speeds_mps, turning_role,
                               lookahead_m=5.0):
    """Apply one source-route command to each Native vehicle before a world tick.

    Release frames are engineering capture inputs. They do not encode which
    driver has statutory priority or whether the exception applies.
    """
    if site.get("crossing_polygon_xy_m") is None:
        raise ValueError("Sourced crossing polygon required for opposite-turn control")
    geometry = check_routes(site.get("routes"), turning_role,
                            site.get("crossing_polygon_xy_m"))
    roles = ("ego", "other")
    if set(actors) != set(roles) or set(progress) != set(roles):
        raise ValueError("Both live Native actors and route indices required")
    if (type(frame_index) is not int or frame_index < 0
            or set(release_frames) != set(roles)
            or any(type(release_frames[role]) is not int or release_frames[role] < 1
                   for role in roles)
            or set(target_speeds_mps) != set(roles)
            or any(type(target_speeds_mps[role]) not in (int, float)
                   or not math.isfinite(target_speeds_mps[role])
                   or target_speeds_mps[role] <= 0 for role in roles)):
        raise ValueError("Finite release schedule and target speeds required")
    decisions = {}
    # Compute both steering paths before applying either command. If geometry or
    # a route index is invalid, no actor receives a partial new command.
    for role in roles:
        pose = actors[role].get_transform()
        location, yaw = pose.location, float(pose.rotation.yaw)
        steer, next_index = steering_command(float(location.x), float(location.y),
                                              yaw, site["routes"][role], progress[role],
                                              lookahead_m=lookahead_m)
        decisions[role] = {"steer": steer, "next_index": next_index,
                           "release_allowed": frame_index >= release_frames[role]}
    for role in roles:
        decision = decisions[role]
        decision["applied_control"] = apply_speed_control(
            carla, actors[role], float(target_speeds_mps[role]),
            not decision["release_allowed"], decision["steer"])
        progress[role] = decision["next_index"]
    return {"frame_index": frame_index, "turning_role": turning_role,
            "geometry": geometry, "decisions": decisions,
            "native_motion_verified": False, "legal_exception_verified": False}
