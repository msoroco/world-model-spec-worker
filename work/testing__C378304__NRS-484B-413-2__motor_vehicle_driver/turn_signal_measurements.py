"""Measure right-turn indication beside a sourced freight-loading zone.

The business/residential 100-foot and other-area 300-foot boundaries are exact.
The module reports a conservative sampled distance from the first observed On
frame to the authored onset; it never treats weather as an excuse.
"""

import hashlib
import json
import math
from pathlib import Path
from right_turn_course import measure_right_turn


FEET_TO_M = 0.3048
REQUIRED = ("drive_history.jsonl", "video_frames.jsonl", "route_context.json",
            "freight-zone-site-source.txt")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite source measurement")
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


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
                "district_source", "freight_loading_zone_source", "turn_onset_frame"):
        if context.get(key) is None:
            raise ValueError("Missing sourced route context: " + key)
    district = context.get("district_type")
    if district not in ("business", "residential", "other"):
        raise ValueError("District class not sourced")
    config_path = root / "config.json"
    if config_path.is_file():
        case_id = json.loads(config_path.read_text()).get("selected_case_id", "")
        expected_district = "other" if case_id.endswith("__other_area_right_at_300ft") else "business"
        if district != expected_district:
            raise ValueError("Exact-case district differs from retained source")
        weather = context.get("native_weather_readback")
        if not isinstance(weather, dict) or any(
                key not in weather or not 0 <= _number(weather[key]) <= 100
                for key in ("cloudiness", "precipitation", "wetness")):
            raise ValueError("Native weather readback missing")
        if (case_id.endswith("__zone_right_wet") and weather["precipitation"] <= 0
                or not case_id.endswith("__zone_right_wet") and weather["precipitation"] != 0):
            raise ValueError("Exact-case precipitation differs from Native readback")
    if (context["freight_loading_zone_source"] != "freight-zone-site-source.txt"
            or context.get("freight_loading_zone_source_sha256") !=
            hashes["freight-zone-site-source.txt"]):
        raise ValueError("Freight-loading-zone context lacks bound source")
    threshold = (100 if district in ("business", "residential") else 300) * FEET_TO_M
    rows, frames = _rows(root / "drive_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete drive/frame history")
    course = measure_right_turn(rows, context)
    if context["turn_onset_frame"] != course["turn_onset_frame"]:
        raise ValueError("Authored turn onset disagrees with measured Native course")
    prior = (-1, -math.inf)
    path = 0.0
    previous_xy = None
    signal_start_path = None
    onset = None
    speeds = []
    seen_off_before_on = False
    prior_indicator = None
    for i, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _number(row.get("time_s"))
        if type(fid) is not int or fid <= prior[0] or time <= prior[1]:
            raise ValueError("Nonmonotone original drive history")
        prior = (fid, time)
        if frame.get("video_frame") != i or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        xy = row.get("ego_position_xy_m")
        if not isinstance(xy, list) or len(xy) != 2:
            raise ValueError("Missing ego path point")
        xy = (_number(xy[0]), _number(xy[1]))
        if previous_xy is not None:
            path += math.dist(xy, previous_xy)
        previous_xy = xy
        indicator = row.get("right_indicator")
        if type(indicator) is not bool:
            raise ValueError("Missing measured right indicator")
        mask = row.get("ego_light_mask")
        if type(mask) is not int or indicator != bool(mask & 16):
            raise ValueError("Right indicator differs from Native light-mask readback")
        if indicator and prior_indicator is False:
            seen_off_before_on = True
            signal_start_path = path
        if not indicator:
            signal_start_path = None
        prior_indicator = indicator
        speeds.append(_number(row.get("ego_speed_mps")))
        if fid == course["turn_onset_frame"]:
            if not seen_off_before_on or signal_start_path is None or not indicator:
                raise ValueError("No fully observed continuous pre-turn right signal")
            onset = {"frame": fid, "time_s": time, "path_length_m": path,
                     "continuous_right_signal_distance_m": path - signal_start_path,
                     "ego_position_xy_m": list(xy)}
            break
    if onset is None:
        raise ValueError("Turn onset absent from original trace")
    return {"format": "worker-continuous-right-turn-signal-distance", "sources": hashes,
            "district_type": district, "required_distance_m": threshold,
            "freight_loading_zone_source": context["freight_loading_zone_source"],
            "turn_onset": onset, "course_measurement": course,
            "observed_continuous_distance_meets_boundary":
                onset["continuous_right_signal_distance_m"] >= threshold - 1e-9,
            "approach_speed_samples_mps": speeds,
            "route_turn_direction_judgment": "sampled rightward heading and outgoing-lane transition; Native geometry still requires review",
            "weather_exception": "none in NRS 484B.413(2)"}
