"""Measure continuous left-indicator path length before a course change.

The business/residential 100-foot and other-area 300-foot boundaries are exact.
The module reports a conservative sampled distance from the first observed On
frame to the authored onset; it never treats weather as an excuse.
"""

import hashlib
import json
import math
from pathlib import Path


FEET_TO_M = 0.3048
REQUIRED = ("drive_history.jsonl", "video_frames.jsonl", "route_context.json")


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
        indicator = row.get("left_indicator")
        if type(indicator) is not bool:
            raise ValueError("Missing measured left indicator")
        if indicator and prior_indicator is False:
            seen_off_before_on = True
            signal_start_path = path
        if not indicator:
            signal_start_path = None
        prior_indicator = indicator
        speeds.append(_number(row.get("ego_speed_mps")))
        if fid == context["turn_onset_frame"]:
            if not seen_off_before_on or signal_start_path is None or not indicator:
                raise ValueError("No fully observed continuous pre-turn left signal")
            onset = {"frame": fid, "time_s": time, "path_length_m": path,
                     "continuous_left_signal_distance_m": path - signal_start_path,
                     "ego_position_xy_m": list(xy)}
            break
    if onset is None:
        raise ValueError("Turn onset absent from original trace")
    return {"format": "worker-continuous-left-turn-signal-distance", "sources": hashes,
            "district_type": district, "required_distance_m": threshold,
            "turn_onset": onset, "observed_continuous_distance_meets_boundary":
                onset["continuous_left_signal_distance_m"] >= threshold - 1e-9,
            "approach_speed_samples_mps": speeds,
            "route_turn_direction_judgment": "unresolved until Native route geometry is reviewed",
            "weather_exception": "none in NRS 484B.413(2)"}
