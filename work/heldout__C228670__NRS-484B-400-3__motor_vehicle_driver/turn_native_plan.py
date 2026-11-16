"""Source-bound Native target plan for the three controlled left-turn cases.

Offsets are engineering probes of original body placement. They are not
statutory distances or compliance classifications.
"""

from math import atan2, hypot, isfinite
import json
from pathlib import Path

from body_position import directed_line, point
from route_survey import load_survey, verify_native_route


ASSIGNMENT = "heldout__C228670__NRS-484B-400-3__motor_vehicle_driver"
OFFSETS_M = {
    "centerline_approach_left_curb_departure": (1.2, 1.2),
    "farther_approach_left_curb_departure": (2.2, 1.2),
    "centerline_approach_farther_departure": (1.2, 2.2),
}


def _right_of(line, distance, *, at_end):
    origin, direction, length = directed_line(line)
    x = origin[0] + (length if at_end else .6 * length) * direction[0]
    y = origin[1] + (length if at_end else .6 * length) * direction[1]
    return [x + distance * direction[1], y - distance * direction[0]]


def prepare(case_id, source_path, expected_sha256):
    prefix = ASSIGNMENT + "__"
    suffix = case_id[len(prefix):] if isinstance(case_id, str) and case_id.startswith(prefix) else ""
    if suffix not in OFFSETS_M:
        raise ValueError("Unknown exact two-way-to-one-way turn case")
    survey = load_survey(source_path, expected_sha256)
    approach_m, departure_m = OFFSETS_M[suffix]
    for field, offset in (("approach_right_half_width_m", approach_m),
                          ("destination_one_way_width_m", departure_m)):
        width = survey.get(field)
        if isinstance(width, bool) or not isinstance(width, (int, float)) or not isfinite(width):
            raise ValueError("Native survey lacks finite road width: " + field)
        if offset + .9 >= width:
            raise ValueError("Vehicle body target cannot fit surveyed roadway: " + field)
    start = point(survey["waypoints"][0]["xy_m"])
    entry = _right_of(survey["approach_centerline_xy_m"], approach_m, at_end=True)
    departure = _right_of(survey["destination_left_curb_xy_m"], departure_m, at_end=False)
    if min(hypot(entry[0]-start[0], entry[1]-start[1]),
           hypot(departure[0]-entry[0], departure[1]-entry[1])) < .5:
        raise ValueError("Surveyed turn targets collapse")
    return {"case_id": case_id, "source_path": str(source_path),
            "source_sha256": expected_sha256, "map_name": survey["map_name"],
            "approach_target_offset_m": approach_m,
            "departure_target_offset_m": departure_m,
            "targets_xy_m": [list(start), entry, departure],
            "native_route_unverified": True,
            "physical_outcome_unverified": True}


def verify_loaded_map(world_map, plan, driving_lane_type):
    survey = load_survey(plan["source_path"], plan["source_sha256"])
    return verify_native_route(world_map, survey, driving_lane_type)


def seal_route_source(world_map, plan, driving_lane_type, output):
    """Retain the exact surveyed source only after Native waypoint validation."""
    waypoints = verify_loaded_map(world_map, plan, driving_lane_type)
    root = Path(output)
    source = root / "route_survey_original.json"
    receipt = root / "route_survey_capture_receipt.json"
    if source.exists() or receipt.exists():
        raise ValueError("Retain prior Native route source")
    raw = Path(plan["source_path"]).read_bytes()
    source.write_bytes(raw)
    recorded = {"case_id": plan["case_id"], "source_path": source.name,
                "source_sha256": plan["source_sha256"],
                "map_name": plan["map_name"], "native_route_verified": True,
                "waypoint_readback": [{"road_id": w.road_id, "lane_id": w.lane_id,
                                       "is_junction": bool(w.is_junction),
                                       "xy_m": [float(w.transform.location.x), float(w.transform.location.y)]}
                                      for w in waypoints],
                "physical_turn_completed": False,
                "public_access_verified": False}
    receipt.write_text(json.dumps(recorded, indent=2) + "\n")
    return recorded


def control_step(position_xy, heading_xy, velocity_xy, target_xy, *, target_speed_mps=4.):
    """Bounded feedback for a sourced physical target, without a success claim."""
    values = (*position_xy, *heading_xy, *velocity_xy, *target_xy, target_speed_mps)
    if not all(isfinite(v) for v in values):
        raise ValueError("Nonfinite Native turn feedback")
    dx, dy = target_xy[0]-position_xy[0], target_xy[1]-position_xy[1]
    length = hypot(dx, dy)
    heading_length = hypot(*heading_xy)
    if length < .2 or heading_length < .1 or not 0 < target_speed_mps <= 10:
        raise ValueError("Invalid Native turn target or engineering speed")
    hx, hy = heading_xy[0]/heading_length, heading_xy[1]/heading_length
    error = atan2(hx*dy-hy*dx, hx*dx+hy*dy)
    speed = hypot(*velocity_xy)
    return {"steer": max(-.5, min(.5, .8*error)),
            "throttle": max(0., min(.4, .22*(target_speed_mps-speed))),
            "brake": max(0., min(.4, .16*(speed-target_speed_mps)))}
