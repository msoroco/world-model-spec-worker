"""Saved-source measurements for the assigned yield-sign nearest-view branch.

Inputs are original observation packets. This module does not decide legal
applicability, immediate hazard, or right-of-way compliance.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def measure(packet: dict) -> dict:
    context = packet["reviewed_context"]
    for name in ("yield_sign_governs_approach", "no_marked_stop_line", "no_near_side_crosswalk",
                 "no_sidewalk_derived_crosswalk", "through_highway_confirmed", "no_officer_control",
                 "no_signal_control", "viewpoint_reviewed"):
        if context.get(name) is not True:
            raise ValueError(f"reviewed context missing {name}")
    samples = packet["samples"]
    if not isinstance(samples, list) or len(samples) < 3:
        raise ValueError("at least three original samples required")
    previous_time = -math.inf
    first_view = None
    crossing = None
    minimum_approach_speed = math.inf
    participant_history = []
    for index, sample in enumerate(samples):
        t = _number(sample["time_s"], "time_s")
        if t <= previous_time:
            raise ValueError("sample times must increase strictly")
        previous_time = t
        speed = _number(sample["ego_speed_mps"], "ego_speed_mps")
        if speed < 0:
            raise ValueError("speed cannot be negative")
        station = _number(sample["ego_front_station_m"], "ego_front_station_m")
        through_station = _number(sample["through_center_station_m"], "through_center_station_m")
        view = sample.get("through_traffic_visible")
        if not isinstance(view, bool):
            raise ValueError("visibility must be an original boolean observation")
        if first_view is None and view:
            first_view = {"index": index, "time_s": t, "ego_front_station_m": station}
        if crossing is None:
            minimum_approach_speed = min(minimum_approach_speed, speed)
            if sample.get("intersection_entry") is True:
                crossing = {"index": index, "time_s": t, "ego_front_station_m": station}
        if not isinstance(sample.get("through_vehicle_within_intersection"), bool):
            raise ValueError("participant occupancy must be observed at every sample")
        participant_history.append({"time_s": t, "through_center_station_m": through_station,
                                    "within_intersection": sample["through_vehicle_within_intersection"]})
    if first_view is None or crossing is None or first_view["index"] >= crossing["index"]:
        raise ValueError("first view must precede intersection entry")
    if samples[0]["through_traffic_visible"]:
        raise ValueError("nearest-view fallback needs a witnessed no-view approach")
    if not any(row["within_intersection"] for row in participant_history[crossing["index"]:]):
        raise ValueError("retain an occupied-through-highway interval during crossing")
    return {
        "kind": "nearest-view-saved-measurement",
        "first_view": first_view,
        "intersection_entry": crossing,
        "minimum_approach_speed_mps": minimum_approach_speed,
        "through_center_station_at_view_m": participant_history[first_view["index"]]["through_center_station_m"],
        "through_vehicle_history": participant_history,
        "sample_count": len(samples),
        "legal_status": "unresolved",
    }


def measure_file(source: Path, output: Path) -> dict:
    raw = source.read_bytes()
    packet = json.loads(raw)
    result = measure(packet)
    result["source"] = {"path": str(source), "sha256": hashlib.sha256(raw).hexdigest()}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    measure_file(args.source, args.output)
