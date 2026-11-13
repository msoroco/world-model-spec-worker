"""Source-bound Native route validation for the two-way to one-way left turn.

The catalog's generic ``road`` label does not establish an intersection.  A
survey identifies the actual XODR lanes; this module checks those lanes again
against the loaded Native map before a construction may use them.
"""

import hashlib
import json
from math import cos, hypot, isfinite, pi, sin
from pathlib import Path


def _point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Survey needs two-dimensional coordinates")
    point = tuple(float(component) for component in value)
    if not all(isfinite(component) for component in point):
        raise ValueError("Survey coordinates must be finite")
    return point


def load_survey(path, expected_sha256):
    path = Path(path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Route survey source hash differs")
    survey = json.loads(raw)
    if survey.get("provenance_kind") != "native_xodr_survey":
        raise ValueError("Route survey needs Native XODR provenance")
    if not survey.get("map_name") or survey.get("intersection_kind") != "public_highway_non_alley":
        raise ValueError("Survey does not identify the qualifying intersection")
    if survey.get("approach_directions") != 2 or survey.get("destination_directions") != 1:
        raise ValueError("Survey needs two-way approach and one-way exit")
    route = survey.get("waypoints")
    if not isinstance(route, list) or len(route) < 3:
        raise ValueError("Survey needs approach, junction and exit waypoints")
    for item in route:
        if not all(key in item for key in ("road_id", "lane_id", "s", "xy_m")):
            raise ValueError("Survey waypoint is incomplete")
        _point(item["xy_m"])
    for key in ("approach_centerline_xy_m", "destination_left_curb_xy_m"):
        line = survey.get(key)
        if not isinstance(line, list) or len(line) != 2:
            raise ValueError("Survey lacks a controlling road line")
        a, b = map(_point, line)
        if hypot(a[0] - b[0], a[1] - b[1]) <= 0:
            raise ValueError("Survey road line is degenerate")
    entry = _point(survey.get("intersection_entry_xy_m"))
    a, b = map(_point, survey["approach_centerline_xy_m"])
    cross = (b[0] - a[0]) * (entry[1] - a[1]) - (b[1] - a[1]) * (entry[0] - a[0])
    if abs(cross) > 1e-4:
        raise ValueError("Intersection entry is off the approach centerline")
    return survey


def verify_native_route(world_map, survey, driving_lane_type):
    """Return checked Native waypoints; no route or direction is inferred."""
    if world_map.name != survey["map_name"]:
        raise ValueError("Loaded Native map differs from survey")
    waypoints = []
    for item in survey["waypoints"]:
        waypoint = world_map.get_waypoint_xodr(item["road_id"], item["lane_id"], item["s"])
        if waypoint is None or waypoint.lane_type != driving_lane_type:
            raise ValueError("Surveyed driving lane is unavailable")
        actual = waypoint.transform.location
        expected = _point(item["xy_m"])
        if hypot(actual.x - expected[0], actual.y - expected[1]) > 0.5:
            raise ValueError("Native waypoint differs from source coordinates")
        waypoints.append(waypoint)
    if not any(waypoint.is_junction for waypoint in waypoints[1:-1]):
        raise ValueError("Surveyed route has no interior Native junction")
    if waypoints[0].road_id == waypoints[-1].road_id:
        raise ValueError("Turn does not enter a different road")
    _verify_road_directions(world_map, waypoints, driving_lane_type)
    return waypoints


def _heading(waypoint):
    angle = waypoint.transform.rotation.yaw * pi / 180
    return cos(angle), sin(angle)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _verify_road_directions(world_map, route, driving_lane_type):
    """Inventory Native driving lanes on each selected road by heading.

    The map's lane inventory is a physical topology check. Public access and
    applicable highway operation still need original source review.
    """
    inventory = [waypoint for waypoint in world_map.generate_waypoints(2.0)
                 if waypoint.lane_type == driving_lane_type and not waypoint.is_junction]
    approach_road = route[0].road_id
    destination_road = route[-1].road_id
    approach = [waypoint for waypoint in inventory if waypoint.road_id == approach_road]
    destination = [waypoint for waypoint in inventory if waypoint.road_id == destination_road]
    if not approach or not destination:
        raise ValueError("Native direction inventory lacks selected roads")
    incoming = _heading(route[0])
    outgoing = _heading(route[-1])
    if not any(_dot(_heading(wp), incoming) > .7 for wp in approach):
        raise ValueError("Native approach has no incoming driving direction")
    if not any(_dot(_heading(wp), incoming) < -.7 for wp in approach):
        raise ValueError("Native approach lacks opposing driving direction")
    if not any(_dot(_heading(wp), outgoing) > .7 for wp in destination):
        raise ValueError("Native exit has no departing driving direction")
    if any(_dot(_heading(wp), outgoing) < -.7 for wp in destination):
        raise ValueError("Native exit has opposing driving direction")
    if any(abs(_dot(_heading(wp), outgoing)) <= .7 for wp in destination):
        raise ValueError("Native exit has ambiguous driving direction")
