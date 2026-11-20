"""Measure continuous right-indicator path length before a course change.

The business/residential 100-foot and other-area 300-foot boundaries are exact.
The module reports a conservative sampled distance from the first observed On
frame to the authored onset; it never treats weather as an excuse.
"""

import hashlib
import json
import math
from pathlib import Path
from contextlib import contextmanager


FEET_TO_M = 0.3048
REQUIRED = ("drive_history.jsonl", "video_frames.jsonl", "route_context.json")


def _waypoint_xy(waypoint):
    location = waypoint.transform.location
    return (_number(location.x), _number(location.y))


def verify_native_right_turn(approach, departure, *, minimum_approach_m=300 * FEET_TO_M,
                             max_step_m=5.0):
    """Validate the Native lane chain before using it for any signaling case.

    District classification is deliberately outside geometry: it needs a
    separately reviewed source, recorded in route_context.json.
    """
    if len(approach) < 3 or len(departure) < 2:
        raise ValueError("Incomplete Native right-turn route")
    incoming_key = (approach[0].road_id, approach[0].lane_id)
    outgoing_key = (departure[0].road_id, departure[0].lane_id)
    if any((wp.road_id, wp.lane_id) != incoming_key for wp in approach):
        raise ValueError("Approach lane or road changes before turn")
    if any((wp.road_id, wp.lane_id) != outgoing_key for wp in departure):
        raise ValueError("Departure lane or road changes after turn")
    if incoming_key[0] == outgoing_key[0]:
        raise ValueError("Right turn needs a distinct outgoing road")
    incoming_xy = [_waypoint_xy(wp) for wp in approach]
    outgoing_xy = [_waypoint_xy(wp) for wp in departure]
    steps = [math.dist(a, b) for a, b in zip(incoming_xy, incoming_xy[1:])]
    if any(not 0 < step <= max_step_m for step in steps):
        raise ValueError("Discontinuous Native approach")
    length = sum(steps)
    if length < minimum_approach_m:
        raise ValueError("Native approach shorter than 300-foot observation span")
    if math.dist(incoming_xy[-1], outgoing_xy[0]) > max_step_m:
        raise ValueError("Native turn connection is discontinuous")
    if any(not 0 < math.dist(a, b) <= max_step_m
           for a, b in zip(outgoing_xy, outgoing_xy[1:])):
        raise ValueError("Discontinuous Native departure")
    first = (incoming_xy[-1][0] - incoming_xy[-2][0],
             incoming_xy[-1][1] - incoming_xy[-2][1])
    last = (outgoing_xy[-1][0] - outgoing_xy[0][0],
            outgoing_xy[-1][1] - outgoing_xy[0][1])
    denominator = math.hypot(*first) * math.hypot(*last)
    if denominator == 0:
        raise ValueError("Zero Native turn vector")
    angle = math.degrees(math.atan2(first[0] * last[1] - first[1] * last[0],
                                    first[0] * last[0] + first[1] * last[1]))
    if not -150 < angle < -30:
        raise ValueError("Native route is not a right turn")
    return {"approach_road_id": incoming_key[0], "approach_lane_id": incoming_key[1],
            "outgoing_road_id": outgoing_key[0], "outgoing_lane_id": outgoing_key[1],
            "direct_approach_m": length, "turn_angle_deg": angle,
            "waypoints": list(approach) + list(departure)}


@contextmanager
def spawn_native_right_turn(world, blueprint, approach, departure):
    route = verify_native_right_turn(approach, departure)
    vehicle = world.try_spawn_actor(blueprint, approach[0].transform)
    if vehicle is None:
        raise ValueError("Native right-turn vehicle spawn failed")
    try:
        observed = world.get_map().get_waypoint(vehicle.get_location(), project_to_road=False)
        if observed is None or (observed.road_id, observed.lane_id) != (
                route["approach_road_id"], route["approach_lane_id"]):
            raise ValueError("Spawned vehicle outside Native approach lane")
        yield {"vehicle": vehicle, "route": route}
    finally:
        vehicle.destroy()


def set_native_right_blinker(vehicle, light_state_type, enabled):
    flag = light_state_type.RightBlinker
    prior = vehicle.get_light_state()
    requested = prior | flag if enabled else prior & ~flag
    vehicle.set_light_state(requested)
    readback = vehicle.get_light_state()
    if bool(readback & flag) != bool(enabled):
        raise ValueError("Native right-indicator readback disagrees with request")
    if (readback & ~flag) != (prior & ~flag):
        raise ValueError("Native light actuation changed unrelated lamps")
    return {"requested_right_indicator": bool(enabled),
            "readback_right_indicator": bool(readback & flag)}


def indicator_request_at_remaining_distance(remaining_m, *, start_m,
                                            interruption_m=None):
    """Return the authored request for an approach station, before actuation.

    `remaining_m` must come from the selected route's cumulative lane distance.
    An interruption interval is a closed pair of remaining distances; it is a
    deliberate case variable and never inferred from the desired legal label.
    """
    remaining = _number(remaining_m)
    start = _number(start_m)
    if remaining < 0 or start <= 0:
        raise ValueError("Invalid route-distance indicator schedule")
    if interruption_m is not None:
        if not isinstance(interruption_m, (list, tuple)) or len(interruption_m) != 2:
            raise ValueError("Invalid indicator interruption interval")
        low, high = map(_number, interruption_m)
        if not 0 <= low < high < start:
            raise ValueError("Indicator interruption must lie inside the active approach")
        if low <= remaining <= high:
            return False
    return remaining <= start


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite source measurement")
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _angle_delta(degrees, reference):
    return (degrees - reference + 180.0) % 360.0 - 180.0


def analyze(root: Path) -> dict:
    root = Path(root)
    hashes = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "route_context.json").read_text())
    for key in ("native_map_id", "approach_road_id", "approach_lane_id",
                "outgoing_road_id", "outgoing_lane_id", "native_route_source",
                "district_source", "turn_onset_frame"):
        if context.get(key) is None:
            raise ValueError("Missing sourced route context: " + key)
    district = context.get("district_type")
    if district not in ("business", "residential", "other"):
        raise ValueError("District class not sourced")
    threshold = (100 if district in ("business", "residential") else 300) * FEET_TO_M
    rows, frames = _rows(root / "drive_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete drive/frame history")
    prior = (-1, -math.inf)
    path = 0.0
    previous_xy = None
    signal_start_path = None
    onset = None
    speeds = []
    seen_off_before_on = False
    prior_indicator = None
    prior_speed = None
    initial_heading = None
    measured_onset_frame = None
    for i, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _number(row.get("time_s"))
        if type(fid) is not int or fid <= prior[0] or time <= prior[1]:
            raise ValueError("Nonmonotone original drive history")
        prior_time = prior[1]
        prior = (fid, time)
        if frame.get("video_frame") != i or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        xy = row.get("ego_position_xy_m")
        if not isinstance(xy, list) or len(xy) != 2:
            raise ValueError("Missing ego path point")
        xy = (_number(xy[0]), _number(xy[1]))
        speed = _number(row.get("ego_speed_mps"))
        if speed < 0:
            raise ValueError("Negative measured speed")
        if previous_xy is not None:
            segment_m = math.dist(xy, previous_xy)
            elapsed_s = time - prior_time
            plausible_m = max(speed, prior_speed) * elapsed_s
            if segment_m > plausible_m + max(0.1, 0.1 * plausible_m):
                raise ValueError("Measured path jump exceeds source speed")
            path += segment_m
        heading = _number(row.get("ego_heading_deg"))
        if previous_xy is not None and math.dist(xy, previous_xy) > 0.01:
            measured_bearing = math.degrees(math.atan2(xy[1] - previous_xy[1],
                                                        xy[0] - previous_xy[0]))
            if abs(_angle_delta(heading, measured_bearing)) > 5.0:
                raise ValueError("Source heading disagrees with measured path bearing")
        previous_xy = xy
        prior_speed = speed
        if initial_heading is None:
            initial_heading = heading
        heading_delta = _angle_delta(heading, initial_heading)
        if measured_onset_frame is None and abs(heading_delta) >= 10.0:
            measured_onset_frame = fid
            if heading_delta >= 0:
                raise ValueError("Measured course change is not a right turn")
        elif measured_onset_frame is None and abs(heading_delta) > 3.0:
            raise ValueError("Unstable pre-turn course heading")
        indicator = row.get("right_indicator")
        if type(indicator) is not bool:
            raise ValueError("Missing measured right indicator")
        if indicator and prior_indicator is False:
            seen_off_before_on = True
            signal_start_path = path
        if not indicator:
            signal_start_path = None
        prior_indicator = indicator
        speeds.append(speed)
        if fid == context["turn_onset_frame"]:
            if measured_onset_frame != fid:
                raise ValueError("Authored turn onset disagrees with measured heading change")
            if not seen_off_before_on or signal_start_path is None or not indicator:
                raise ValueError("No fully observed continuous pre-turn right signal")
            onset = {"frame": fid, "time_s": time, "path_length_m": path,
                     "continuous_right_signal_distance_m": path - signal_start_path,
                     "ego_position_xy_m": list(xy), "heading_delta_deg": heading_delta,
                     "onset_method": "first_source_heading_change_at_least_10deg"}
            break
    if onset is None:
        raise ValueError("Turn onset absent from original trace")
    return {"format": "worker-continuous-right-turn-signal-distance", "sources": hashes,
            "district_type": district, "required_distance_m": threshold,
            "turn_onset": onset, "observed_continuous_distance_meets_boundary":
                onset["continuous_right_signal_distance_m"] >= threshold - 1e-9,
            "approach_speed_samples_mps": speeds,
            "route_turn_direction_judgment": "unresolved until Native route geometry is reviewed",
            "weather_exception": "none in NRS 484B.413(2)"}
