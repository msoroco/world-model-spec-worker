"""Measure original rail-crossing episode and trailing-end clearance."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "ego_front", "rail_side", "opposite_side"}
COMPLETE_CLEARANCE_M = 4.572  # Statutory 15 feet.


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def measure(context, rows):
    if context.get("source_kind") != "native_rail_vehicle_and_opposite_space_readback":
        raise ValueError("Missing Native rail and opposite-space readback")
    for key in ("native_map_sha256", "rail_geometry_sha256", "vehicle_extent_sha256",
                "opposite_space_source_sha256"):
        value = context.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"Missing source hash: {key}")
    if context.get("crossing_kind") != "at_grade":
        raise ValueError("At-grade railroad crossing not sourced")
    near = finite(context.get("entry_rail_x_m"), "entry rail")
    far = finite(context.get("clearance_reference_rail_x_m"), "clearance reference rail")
    length = finite(context.get("vehicle_length_m"), "vehicle length")
    opposite_space = finite(context.get("opposite_side_space_before_entry_m"), "pre-entry opposite space")
    if far <= near or length <= 0 or opposite_space < 0:
        raise ValueError("Invalid rail or vehicle geometry")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    previous_native = None
    entered = []
    stopped = []
    clearance = []
    causes = []
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
        center = finite(row.get("vehicle_center_x_m"), "vehicle center")
        speed = finite(row.get("observed_speed_mps"), "observed speed")
        if speed < 0:
            raise ValueError("Negative observed speed")
        trailing = center - length / 2
        entered.append(center + length / 2 >= near)
        stopped.append(speed <= 0.10)
        clearance.append(trailing - far)
        cause = row.get("stop_cause_source")
        if cause not in {None, "opposite_space_observed", "undercarriage_observed", "other_observed"}:
            raise ValueError("Unknown stop cause source")
        causes.append(cause)
    entries = [i for i in range(1, FRAMES) if entered[i] and not entered[i - 1]]
    if len(entries) != 1:
        raise ValueError("Expected one sourced crossing entry")
    entry = entries[0]
    preclear_stops = [i for i in range(entry, FRAMES)
                      if stopped[i] and clearance[i] < COMPLETE_CLEARANCE_M]
    space_cause_frames = [i for i in preclear_stops if causes[i] == "opposite_space_observed"]
    return {"format": "worker-source-rail-crossing-episode-measurement",
            "frame_count": FRAMES, "rate_hz": RATE_HZ,
            "crossing_entry_frame": entry,
            "pre_entry_opposite_space_m": opposite_space,
            "maximum_trailing_end_clearance_past_reference_rail_m": max(clearance[entry:]),
            "trailing_end_reached_15_feet": any(value >= COMPLETE_CLEARANCE_M for value in clearance[entry:]),
            "stopped_before_15_foot_clearance_frames": len(preclear_stops),
            "opposite_space_cause_observed_frames": len(space_cause_frames),
            "undercarriage_clearance_alternative": "pending_separate_source_review",
            "legal_compliance": "unassessed",
            "limitations": ["Reference rail identity and trailing-end geometry require independent original review",
                            "Pre-entry space and attributed stop cause need original source review",
                            "A speed threshold here is an engineering stop detector, not a statutory duration definition"]}


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
