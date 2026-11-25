"""Source-bound bus-stop geometry and traffic observations; no legal verdict."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}
LIMIT_M = 0.4572  # The statute's eighteen inches, exactly converted to metres.


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def measure(context, rows):
    if context.get("source_kind") != "native_bus_wheel_curb_and_traffic_readback":
        raise ValueError("Missing Native bus/wheel/curb/traffic readback")
    for key in ("native_map_sha256", "curb_calibration_sha256", "bus_classification_sha256",
                "wheel_geometry_sha256", "loading_zone_sha256"):
        value = context.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"Missing source hash: {key}")
    if context.get("vehicle_class") != "non_tour_bus":
        raise ValueError("Covered non-tour bus classification not sourced")
    if context.get("location_kind") not in {"bus_stop", "bus_stand", "passenger_loading_zone", "origin", "destination"}:
        raise ValueError("Qualifying loading location not sourced")
    if context.get("public_street") is not True:
        raise ValueError("Public street status not sourced")
    curb_y = finite(context.get("curb_face_y_m"), "curb face")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native capture")
    previous_native = None
    loading = []
    wheel_gap = []
    heading = []
    traffic_speed = []
    traffic_delay = []
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
        bus_speed = finite(row.get("bus_observed_speed_mps"), "bus speed")
        other_speed = finite(row.get("other_vehicle_observed_speed_mps"), "other vehicle speed")
        delay = finite(row.get("other_vehicle_delay_s"), "other vehicle delay")
        if min(bus_speed, other_speed, delay) < 0:
            raise ValueError("Negative speed or delay")
        stopped_loading = bus_speed <= 0.10 and row.get("loading_activity_observed") is True
        loading.append(stopped_loading)
        wheel_gap.append(abs(finite(row.get("right_front_wheel_contact_y_m"), "front wheel contact") - curb_y))
        heading.append(abs(finite(row.get("bus_curb_heading_difference_deg"), "heading difference")))
        traffic_speed.append(other_speed)
        traffic_delay.append(delay)
    intervals = []
    start = None
    for index, active in enumerate(loading + [False]):
        if active and start is None:
            start = index
        elif not active and start is not None:
            intervals.append([start, index - 1])
            start = None
    longest = max(intervals, key=lambda pair: pair[1] - pair[0], default=None)
    if longest is None or longest[1] - longest[0] + 1 < 100:
        raise ValueError("No measured five-second stopped loading interval")
    selected = slice(longest[0], longest[1] + 1)
    gaps = wheel_gap[selected]
    return {"format": "worker-source-bus-loading-measurement", "frame_count": FRAMES,
            "rate_hz": RATE_HZ, "stopped_loading_interval_frames": longest,
            "wheel_to_curb_gap_m_range": [min(gaps), max(gaps)],
            "wheel_to_curb_gap_inches_range": [min(gaps) / 0.0254, max(gaps) / 0.0254],
            "all_loading_frames_within_18_inches": all(g <= LIMIT_M for g in gaps),
            "heading_difference_deg_range": [min(heading[selected]), max(heading[selected])],
            "other_vehicle_speed_mps_range": [min(traffic_speed), max(traffic_speed)],
            "other_vehicle_delay_s_range": [min(traffic_delay), max(traffic_delay)],
            "approximately_parallel": "requires_independent_judgment",
            "unduly_impede": "requires_independent_judgment",
            "legal_compliance": "unassessed",
            "limitations": ["Fixture values do not establish original Native provenance",
                            "Wheel contact and curb face need independently reviewed source geometry",
                            "Traffic delay is retained without a fabricated undue-impedance cutoff"]}


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
