"""Construct the opposite-approach left-turn exception candidate lazily.

The caller supplies a source-reviewed Native site, route points, transforms and
blueprints. Angular bounds are construction checks, not statutory definitions.
"""

from contextlib import contextmanager
import math
from shapely.geometry import Point, Polygon

from route_control import steering_command
from yield_controller import apply_speed_control


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
                               release_frames, target_speeds_mps, turning_role):
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
                                              yaw, site["routes"][role], progress[role])
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
