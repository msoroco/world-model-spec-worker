"""Measure source-bound motorcycle position between vehicles in adjacent lanes."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "rider_front", "lane_side", "traffic_rear"}


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def box(value, name):
    if not isinstance(value, dict) or set(value) != {"min_x", "max_x", "min_y", "max_y"}:
        raise ValueError(f"Missing {name} footprint")
    result = {key: finite(item, f"{name}.{key}") for key, item in value.items()}
    if result["min_x"] >= result["max_x"] or result["min_y"] >= result["max_y"]:
        raise ValueError(f"Invalid {name} footprint")
    return result


def x_overlap(a, b):
    return min(a["max_x"], b["max_x"]) > max(a["min_x"], b["min_x"])


def center_y(a):
    return (a["min_y"] + a["max_y"]) / 2


def measure(context, rows):
    if context.get("source_kind") != "native_adjacent_lane_and_actor_readback":
        raise ValueError("Missing Native lane and actor readback")
    for key in ("native_map_sha256", "lane_adjacency_sha256", "motorcycle_identity_sha256",
                "left_vehicle_identity_sha256", "right_vehicle_identity_sha256"):
        value = context.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"Missing source hash: {key}")
    if context.get("subject_kind") not in {"motorcycle", "moped"}:
        raise ValueError("Motorcycle or moped identity not sourced")
    if context.get("adjacent_lane_ids") != ["lane_left", "lane_right"]:
        raise ValueError("Adjacent traffic lanes not sourced")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    previous_native = None
    between = []
    left_speeds = []
    right_speeds = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("video_frame") != index:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (previous_native is not None and native <= previous_native):
            raise ValueError("Native frame identity gap")
        previous_native = native
        if abs(finite(row.get("time_s"), "Native time") - index / RATE_HZ) > 1e-6:
            raise ValueError("Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[name] != index for name in CAMERAS):
            raise ValueError("Four source camera frame join failed")
        if row.get("left_vehicle_lane_id") != "lane_left" or row.get("right_vehicle_lane_id") != "lane_right":
            raise ValueError("Surrounding vehicles do not occupy sourced adjacent lanes")
        subject = box(row.get("subject_footprint_m"), "subject")
        left = box(row.get("left_vehicle_footprint_m"), "left vehicle")
        right = box(row.get("right_vehicle_footprint_m"), "right vehicle")
        left_speed = finite(row.get("left_vehicle_speed_mps"), "left speed")
        right_speed = finite(row.get("right_vehicle_speed_mps"), "right speed")
        if left_speed < 0 or right_speed < 0:
            raise ValueError("Negative surrounding vehicle speed")
        left_speeds.append(left_speed)
        right_speeds.append(right_speed)
        between.append(center_y(left) < center_y(subject) < center_y(right)
                       and x_overlap(subject, left) and x_overlap(subject, right))
    intervals = []
    start = None
    for index, active in enumerate(between + [False]):
        if active and start is None:
            start = index
        elif not active and start is not None:
            intervals.append([start, index - 1])
            start = None
    return {"format": "worker-source-adjacent-vehicle-position-measurement",
            "frame_count": FRAMES, "rate_hz": RATE_HZ,
            "between_vehicle_intervals": intervals, "between_vehicle_frames": sum(between),
            "left_vehicle_speed_mps_range": [min(left_speeds), max(left_speeds)],
            "right_vehicle_speed_mps_range": [min(right_speeds), max(right_speeds)],
            "police_duty_exception": "requires_independent_source_review",
            "legal_compliance": "unassessed",
            "limitations": ["Lateral centre ordering and body overlap are measurements, not a legal lane-splitting cutoff",
                            "Lane adjacency, actor identity and police-duty status need original source review"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    context = json.loads(args.context.read_text())
    rows = [json.loads(line) for line in args.trace.read_text().splitlines() if line]
    args.output.write_text(json.dumps(measure(context, rows), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
