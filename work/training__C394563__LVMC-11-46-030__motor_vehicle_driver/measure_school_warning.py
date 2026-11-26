"""Source-bound 30-second school-lane warning, stop and release measurement."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


FRAMES = 600
RATE_HZ = 20
FEET_PER_METRE = 3.280839895013123
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}
WARNING_ROLES = {"signal_device", "flagman", "other_person"}
RELEASES = {"signal_stopped", "signal_raised", "signal_removed",
            "flagman_go", "flagman_left", "person_go", "person_left"}


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def sha(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"Missing source hash: {name}")


def measure(context, rows):
    if context.get("source_kind") != "original_native_school_warning_readback":
        raise ValueError("Original school warning source missing")
    for name in ("native_map_sha256", "school_lane_geometry_sha256", "vehicle_extent_sha256",
                 "warning_actor_sha256", "warning_state_source_sha256", "child_presence_source_sha256"):
        sha(context.get(name), name)
    if context.get("school_pedestrian_lane_survey") is not True:
        raise ValueError("School pedestrian lane not sourced")
    lane_near_x = finite(context.get("nearest_lane_side_x_m"), "nearest lane side")
    length = finite(context.get("vehicle_length_m"), "vehicle length")
    if length <= 0:
        raise ValueError("Vehicle extent invalid")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    previous_native = None
    centers, speeds, warning, releases = [], [], [], []
    roles = set()
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
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[c] != index for c in CAMERAS):
            raise ValueError("Four source camera frame join failed")
        center = finite(row.get("vehicle_center_x_m"), "vehicle center")
        speed = finite(row.get("observed_speed_mps"), "observed speed")
        if speed < 0:
            raise ValueError("Negative speed")
        role = row.get("warning_role")
        if role not in WARNING_ROLES:
            raise ValueError("Warning actor role missing")
        roles.add(role)
        if row.get("warning_active") not in (True, False):
            raise ValueError("Warning state source missing")
        if row.get("children_about_to_cross_or_crossing") not in (True, False):
            raise ValueError("Children warning context missing")
        release = row.get("release_event")
        if release is not None and release not in RELEASES:
            raise ValueError("Unknown statutory release event")
        allowed = {"signal_device": {"signal_stopped", "signal_raised", "signal_removed"},
                   "flagman": {"flagman_go", "flagman_left"},
                   "other_person": {"person_go", "person_left"}}
        if release is not None and release not in allowed[role]:
            raise ValueError("Release event and warning role differ")
        centers.append(center)
        speeds.append(speed)
        warning.append(row["warning_active"] and row["children_about_to_cross_or_crossing"])
        releases.append(release)
    if len(roles) != 1:
        raise ValueError("Warning actor changed within comparison")
    if not any(warning):
        raise ValueError("No sourced warning of children")
    stop_frames = [i for i in range(1, FRAMES - 1)
                   if warning[i] and speeds[i - 1] <= 0.10 and speeds[i] <= 0.10 and speeds[i + 1] <= 0.10]
    if not stop_frames:
        raise ValueError("No observed complete cessation under warning")
    stop = stop_frames[0]
    first_release = next((i for i, event in enumerate(releases) if event is not None), None)
    first_proceed = next((i for i in range(stop + 1, FRAMES)
                          if speeds[i] > 0.10 and centers[i] > centers[stop] + 0.5), None)
    front = lane_near_x - (centers[stop] + length / 2)
    centre = lane_near_x - centers[stop]
    rear = lane_near_x - (centers[stop] - length / 2)
    return {
        "format": "worker-source-school-warning-stop-measurement",
        "frame_count": FRAMES, "rate_hz": RATE_HZ,
        "warning_role": next(iter(roles)),
        "first_stop_frame": stop,
        "stop_distance_to_nearest_school_lane_side_ft": {
            "front": front * FEET_PER_METRE,
            "centre": centre * FEET_PER_METRE,
            "rear": rear * FEET_PER_METRE,
        },
        "first_release_frame": first_release,
        "first_release_event": releases[first_release] if first_release is not None else None,
        "first_proceed_frame": first_proceed,
        "proceeded_before_observed_release": first_proceed is not None and (first_release is None or first_proceed < first_release),
        "statutory_stop_distance_ft": 50,
        "legal_compliance": "unassessed",
        "limitations": [
            "Stop detector is an engineering threshold, not a legal minimum duration",
            "The statute does not select a front, centre, or rear vehicle reference point",
            "Release and child-warning meaning require original actor and pixel review",
            "Commanded release cannot substitute for an observed source event",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.trace.read_text().splitlines() if line]
    args.output.write_text(json.dumps(measure(json.loads(args.context.read_text()), rows), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
