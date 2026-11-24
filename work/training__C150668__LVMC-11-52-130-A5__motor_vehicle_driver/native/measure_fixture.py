"""Measure stop history against sourced sidewalk elevator/chute side extents."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "ego_front", "fixture_side", "traffic_rear"}
SIDE_BAND_M = 1.524  # Statutory five feet, exactly converted to metres.


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def bounds(value, name):
    if not isinstance(value, dict) or set(value) != {"min_x", "max_x", "min_y", "max_y"}:
        raise ValueError(f"Missing {name} bounds")
    result = {key: finite(item, f"{name}.{key}") for key, item in value.items()}
    if result["min_x"] >= result["max_x"] or result["min_y"] >= result["max_y"]:
        raise ValueError(f"Invalid {name} bounds")
    return result


def side_gap(vehicle, fixture):
    if vehicle["max_x"] < fixture["min_x"]:
        return fixture["min_x"] - vehicle["max_x"]
    if fixture["max_x"] < vehicle["min_x"]:
        return vehicle["min_x"] - fixture["max_x"]
    return 0.0


def measure(context, rows):
    if context.get("source_kind") != "native_sidewalk_fixture_and_vehicle_readback":
        raise ValueError("Missing Native fixture and vehicle readback")
    for key in ("native_map_sha256", "fixture_identity_sha256", "fixture_geometry_sha256", "sidewalk_geometry_sha256"):
        value = context.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"Missing source hash: {key}")
    if context.get("fixture_kind") not in {"sidewalk_elevator", "sidewalk_chute"}:
        raise ValueError("Sidewalk elevator or chute identity not sourced")
    fixture = bounds(context.get("fixture_bounds_m"), "fixture")
    sidewalk = bounds(context.get("sidewalk_bounds_m"), "sidewalk")
    if not (sidewalk["min_x"] <= fixture["min_x"] < fixture["max_x"] <= sidewalk["max_x"]
            and sidewalk["min_y"] <= fixture["min_y"] < fixture["max_y"] <= sidewalk["max_y"]):
        raise ValueError("Fixture not contained in sourced sidewalk")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    previous_native = None
    at_rest = []
    side_distance = []
    direct_front = []
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
        vehicle = bounds(row.get("vehicle_footprint_m"), "vehicle footprint")
        speed = finite(row.get("observed_vehicle_speed_mps"), "observed vehicle speed")
        if speed < 0:
            raise ValueError("Negative observed speed")
        at_rest.append(speed <= 0.10)
        side_distance.append(side_gap(vehicle, fixture))
        direct_front.append(vehicle["min_x"] < fixture["max_x"] and vehicle["max_x"] > fixture["min_x"]
                            and vehicle["max_y"] <= fixture["min_y"])
    intervals = []
    start = None
    for index, active in enumerate(at_rest + [False]):
        if active and start is None:
            start = index
        elif not active and start is not None:
            intervals.append([start, index - 1])
            start = None
    longest = max(intervals, key=lambda pair: pair[1] - pair[0], default=None)
    if longest is None or longest[1] - longest[0] + 1 < 100:
        raise ValueError("No measured five-second stop interval")
    selected = slice(longest[0], longest[1] + 1)
    gaps = side_distance[selected]
    fronts = direct_front[selected]
    return {"format": "worker-source-sidewalk-fixture-stop-measurement",
            "frame_count": FRAMES, "rate_hz": RATE_HZ, "rest_interval_frames": longest,
            "side_clearance_m_range_at_rest": [min(gaps), max(gaps)],
            "within_five_foot_side_band_at_rest": any(
                0 < gap and (gap <= SIDE_BAND_M or math.isclose(gap, SIDE_BAND_M, rel_tol=0, abs_tol=1e-9))
                for gap in gaps),
            "directly_in_front_frame_count_at_rest": sum(fronts),
            "physical_result": "pending_original_source_review", "legal_compliance": "unassessed",
            "limitations": ["Fixture identity and front orientation need independent source review",
                            "Traffic conflict, officer and device directions require separate source evidence",
                            "The side-band metric does not decide the separate directly-in-front branch"]}


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
