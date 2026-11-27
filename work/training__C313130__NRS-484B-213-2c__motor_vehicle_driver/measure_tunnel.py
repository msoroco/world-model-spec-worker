"""Source-bound 30-second tunnel approach measurement; no legal verdict."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


FRAMES = 600
RATE_HZ = 20
METRES_IN_100_FEET = 30.48
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def sha(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"Missing source hash: {name}")


def measure(context, rows):
    if context.get("source_kind") != "original_native_tunnel_map_and_ray_readback":
        raise ValueError("Missing original Native tunnel source")
    for name in ("native_map_sha256", "portal_geometry_sha256", "road_direction_survey_sha256",
                 "centreline_geometry_sha256", "vehicle_extent_sha256", "sight_ray_source_sha256"):
        sha(context.get(name), name)
    if context.get("structure_kind") != "tunnel":
        raise ValueError("Tunnel identity not sourced")
    portal_x = finite(context.get("approach_portal_x_m"), "portal position")
    centre_y = finite(context.get("highway_centre_y_m"), "highway centre")
    if context.get("one_way_native_survey") not in (True, False):
        raise ValueError("One-way highway status not sourced")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    previous_native = None
    in_zone = []
    left_of_centre = []
    occluded = []
    sight_brackets = []
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
        body = row.get("body_xy_m")
        if not isinstance(body, list) or len(body) != 4 or any(
            not isinstance(point, list) or len(point) != 2 for point in body
        ):
            raise ValueError("Full vehicle body source missing")
        points = [(finite(point[0], "body x"), finite(point[1], "body y")) for point in body]
        speed = finite(row.get("observed_speed_mps"), "observed speed")
        if speed < 0:
            raise ValueError("Negative observed speed")
        front = max(point[0] for point in points)
        rear = min(point[0] for point in points)
        distance = portal_x - front
        zone = speed > 0.10 and rear < portal_x and 0 <= distance <= METRES_IN_100_FEET
        in_zone.append(zone)
        left_of_centre.append(min(point[1] for point in points) > centre_y)
        ray = row.get("incoming_lane_sight_ray")
        if not isinstance(ray, dict) or ray.get("status") not in {"blocked", "clear_to_limit", "unknown"}:
            raise ValueError("Incoming-lane sight ray source missing")
        lower = finite(ray.get("clear_lower_bound_m"), "sight lower bound")
        upper = ray.get("blocker_upper_bound_m")
        if upper is not None:
            upper = finite(upper, "sight upper bound")
        if lower < 0 or (upper is not None and upper < lower):
            raise ValueError("Invalid sight bracket")
        if ray["status"] == "blocked" and upper is None:
            raise ValueError("Blocked ray lacks blocker bracket")
        if ray["status"] == "clear_to_limit" and upper is not None:
            raise ValueError("Clear ray cannot name blocker")
        occluded.append(ray["status"] == "blocked")
        if zone:
            sight_brackets.append({"frame": index, "status": ray["status"],
                                   "clear_lower_bound_m": lower, "blocker_upper_bound_m": upper})
    if not any(in_zone):
        raise ValueError("No approach inside 100-foot tunnel zone")
    return {
        "format": "worker-source-tunnel-approach-measurement",
        "frame_count": FRAMES, "rate_hz": RATE_HZ,
        "one_way_highway_surveyed": context["one_way_native_survey"],
        "within_100_ft_driving_frames": sum(in_zone),
        "left_of_centre_within_zone_frames": sum(z and left for z, left in zip(in_zone, left_of_centre)),
        "blocked_sight_within_zone_frames": sum(z and blocked for z, blocked in zip(in_zone, occluded)),
        "left_and_blocked_within_zone_frames": sum(z and left and blocked for z, left, blocked in zip(in_zone, left_of_centre, occluded)),
        "sight_brackets_in_zone": sight_brackets,
        "legal_view_obstructed": "independent_judgment_required",
        "legal_compliance": "unassessed",
        "limitations": [
            "Virtual incoming-lane sight rays are a source-preserving proxy, not real driver-eye perception",
            "Clear to range is a lower bound and does not identify an occluder at that range",
            "A sampled body wholly left of centre is a conservative engineering detector, not a legal lateral cutoff",
            "Between-frame crossing and tunnel identity need original Native review",
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
