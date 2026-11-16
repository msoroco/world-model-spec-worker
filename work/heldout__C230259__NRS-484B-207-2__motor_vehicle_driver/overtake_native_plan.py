"""Source-bound two-vehicle Native plan for the first exact overtaking case."""

import hashlib
import json
from math import atan2, hypot, isfinite
from pathlib import Path

ASSIGNMENT = "heldout__C230259__NRS-484B-207-2__motor_vehicle_driver"
CASE = ASSIGNMENT + "__observed_gives_way_holds_speed"


def _point(value, name):
    if (not isinstance(value, list) or len(value) != 2 or
            not all(isinstance(x, (int, float)) and not isinstance(x, bool) and isfinite(x) for x in value)):
        raise ValueError("Invalid source " + name)
    return [float(x) for x in value]


def load_site(path, sha256):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("Native overtaking site SHA-256 mismatch")
    site = json.loads(raw)
    if not isinstance(site, dict) or not site.get("map_name") or site.get("road_kind") != "road":
        raise ValueError("Original road site identity missing")
    start = _point(site.get("ego_start_xy_m"), "ego start")
    passing = _point(site.get("overtaker_start_xy_m"), "overtaker start")
    forward = _point(site.get("forward_xy"), "travel direction")
    length = hypot(*forward)
    if not .99 <= length <= 1.01:
        raise ValueError("Source travel direction must be unit length")
    forward = [x / length for x in forward]
    right = [forward[1], -forward[0]]
    delta = [passing[i] - start[i] for i in (0, 1)]
    longitudinal = sum(delta[i] * forward[i] for i in (0, 1))
    lateral = sum(delta[i] * right[i] for i in (0, 1))
    if not -20. <= longitudinal <= -6. or not -5. <= lateral <= -2.:
        raise ValueError("Overtaker must begin behind and to the left")
    for name in ("ego_road_id", "ego_lane_id", "overtaker_road_id", "overtaker_lane_id"):
        if type(site.get(name)) is not int:
            raise ValueError("Original waypoint identity missing: " + name)
    width = site.get("ego_right_clearance_m")
    if isinstance(width, bool) or not isinstance(width, (int, float)) or not isfinite(width) or width < 1.5:
        raise ValueError("No surveyed clearance for rightward engineering target")
    return site, start, passing, forward, right


def prepare(case_id, source, sha256):
    if case_id != CASE:
        raise ValueError("First exact overtaking case required")
    site, ego, passing, forward, right = load_site(source, sha256)
    project = lambda point, advance, shift: [point[i] + forward[i] * advance + right[i] * shift for i in (0, 1)]
    return {"case_id": case_id, "site_source": str(source), "site_sha256": sha256,
            "map_name": site["map_name"], "ego_start_xy_m": ego,
            "overtaker_start_xy_m": passing, "forward_xy": forward,
            "ego_target_xy_m": project(ego, 22., 0.6),
            "overtaker_target_xy_m": project(passing, 45., 0.),
            "ego_target_speed_mps": 4., "overtaker_target_speed_mps": 8.,
            "notice_path": "original driver-reference camera and participant positions; observation unresolved",
            "physical_completion_claimed": False, "legal_conclusion": None}


def verify_loaded_site(world_map, plan, driving_lane_type, location_factory):
    site, ego_xy, overtaker_xy, _, _ = load_site(plan["site_source"], plan["site_sha256"])
    if world_map.name != site["map_name"]:
        raise ValueError("Loaded Native map differs from surveyed site")
    result = []
    for label, xy in (("ego", ego_xy), ("overtaker", overtaker_xy)):
        location = location_factory(x=xy[0], y=xy[1], z=0.)
        waypoint = world_map.get_waypoint(location, project_to_road=False, lane_type=driving_lane_type)
        if waypoint is None or waypoint.road_id != site[label + "_road_id"] or waypoint.lane_id != site[label + "_lane_id"]:
            raise ValueError("Loaded Native " + label + " waypoint differs from surveyed site")
        if hypot(waypoint.transform.location.x - xy[0], waypoint.transform.location.y - xy[1]) > .35:
            raise ValueError("Loaded Native " + label + " location differs from surveyed site")
        result.append(waypoint)
    return result


def control(position_xy, forward_xy, velocity_xy, target_xy, target_speed_mps):
    values = (*position_xy, *forward_xy, *velocity_xy, *target_xy, target_speed_mps)
    if not all(isfinite(x) for x in values) or not 0 < target_speed_mps <= 12:
        raise ValueError("Invalid original controller input")
    dx, dy = target_xy[0] - position_xy[0], target_xy[1] - position_xy[1]
    distance = hypot(dx, dy)
    if distance < .3 or hypot(*forward_xy) < .9:
        return {"steer": 0., "throttle": 0., "brake": 1.}
    turn = atan2(forward_xy[0] * dy - forward_xy[1] * dx,
                 forward_xy[0] * dx + forward_xy[1] * dy)
    speed = hypot(*velocity_xy)
    return {"steer": max(-.45, min(.45, .75 * turn)),
            "throttle": max(0., min(.45, .2 * (target_speed_mps - speed))),
            "brake": max(0., min(.45, .2 * (speed - target_speed_mps)))}
