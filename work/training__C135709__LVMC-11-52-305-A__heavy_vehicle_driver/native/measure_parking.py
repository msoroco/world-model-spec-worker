"""Source-bound parking geometry measurement; never a legal verdict."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

RATE_HZ = 20
FRAMES = 600
CAMERAS = ("overview", "ego_front", "curb", "rear")
FEET_TO_METRES = 0.3048
POUNDS_TO_KG = 0.45359237


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def rectangle(raw, name):
    if not isinstance(raw, dict) or set(raw) != {"min_x", "max_x", "min_y", "max_y"}:
        raise ValueError(f"Missing {name} rectangle")
    box = {key: finite(value, f"{name}.{key}") for key, value in raw.items()}
    if box["min_x"] >= box["max_x"] or box["min_y"] >= box["max_y"]:
        raise ValueError(f"Invalid {name} rectangle")
    return box


def overlap(a, b):
    return min(a["max_x"], b["max_x"]) > max(a["min_x"], b["min_x"]) and min(a["max_y"], b["max_y"]) > max(a["min_y"], b["min_y"])


def measure(context, rows):
    """Measure physical geometry and rest; legal park status is separately reviewed."""
    if context.get("source_kind") != "native_map_and_external_status_readback":
        raise ValueError("Missing Native map and external park-status source")
    for key in ("native_map_sha256", "park_status_document_sha256", "vehicle_specification_sha256"):
        value = context.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"Missing source hash: {key}")
    if context.get("vehicle_class") != "commercial_motor_vehicle":
        raise ValueError("Commercial vehicle class is not sourced")
    length = finite(context.get("vehicle_overall_length_m"), "overall length")
    weight = finite(context.get("vehicle_unladen_mass_kg"), "unladen mass")
    if length <= 0 or weight <= 0:
        raise ValueError("Invalid vehicle dimensions")
    length_at_least_24_feet = length >= 24 * FEET_TO_METRES
    mass_over_8000_pounds = weight > 8000 * POUNDS_TO_KG
    street = rectangle(context.get("street_bounds_m"), "street")
    park = rectangle(context.get("park_bounds_m"), "park")
    if context.get("park_status") != "public_park":
        raise ValueError("Public park status is not sourced")
    # The street and park must share a boundary, not overlap in area.
    shared_x = min(street["max_x"], park["max_x"]) > max(street["min_x"], park["min_x"])
    shared_y = min(street["max_y"], park["max_y"]) > max(street["min_y"], park["min_y"])
    touches_y = street["max_y"] == park["min_y"] or park["max_y"] == street["min_y"]
    touches_x = street["max_x"] == park["min_x"] or park["max_x"] == street["min_x"]
    if not ((shared_x and touches_y) or (shared_y and touches_x)) or overlap(street, park):
        raise ValueError("Park and street do not share a surveyed boundary")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    rest = []
    adjacent = []
    previous_native = None
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("video_frame") != index:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (previous_native is not None and native <= previous_native):
            raise ValueError("Native frame identity gap")
        previous_native = native
        time_s = finite(row.get("time_s"), "time_s")
        if abs(time_s - index / RATE_HZ) > 1e-6:
            raise ValueError("Native trace time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or tuple(sorted(cameras)) != tuple(sorted(CAMERAS)):
            raise ValueError("Missing four source camera identities")
        if any(type(cameras[camera]) is not int or cameras[camera] != index for camera in CAMERAS):
            raise ValueError("Camera frame join failed")
        speed = finite(row.get("observed_speed_mps"), "observed speed")
        footprint = rectangle(row.get("vehicle_footprint_m"), "vehicle footprint")
        if speed < 0 or not overlap(footprint, street):
            raise ValueError("Invalid speed or vehicle outside street")
        rest.append(speed <= 0.10)
        # Position relative to the park frontage is a geometry observation.
        adjacent.append(min(footprint["max_x"], park["max_x"]) > max(footprint["min_x"], park["min_x"]))
    rest_runs = []
    start = None
    for index, stopped in enumerate(rest + [False]):
        if stopped and start is None:
            start = index
        elif not stopped and start is not None:
            rest_runs.append((start, index - 1))
            start = None
    longest = max(rest_runs, key=lambda run: run[1] - run[0], default=None)
    if longest is None or longest[1] - longest[0] + 1 < RATE_HZ * 5:
        raise ValueError("No measured five-second parking interval")
    during_rest = adjacent[longest[0]:longest[1] + 1]
    return {
        "format": "worker-source-parking-measurement",
        "source_kind": context["source_kind"],
        "source_hashes": {key: context[key] for key in ("native_map_sha256", "park_status_document_sha256", "vehicle_specification_sha256")},
        "frame_count": FRAMES,
        "rate_hz": RATE_HZ,
        "rest_interval_frames": list(longest),
        "rest_duration_s": (longest[1] - longest[0] + 1) / RATE_HZ,
        "park_frontage_overlap_at_rest": all(during_rest),
        "park_frontage_overlap_count": sum(during_rest),
        "vehicle_overall_length_m": length,
        "vehicle_unladen_mass_kg": weight,
        "length_at_least_24_feet": length_at_least_24_feet,
        "unladen_mass_over_8000_pounds": mass_over_8000_pounds,
        "size_or_weight_scope_observed": length_at_least_24_feet or mass_over_8000_pounds,
        "legal_compliance": "unassessed",
        "limitations": ["Source hashes require independent origin review", "Loading, permission and service exceptions require separate evidence", "A rectangle proxy does not decide statutory adjacency"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    context = json.loads(args.context.read_text())
    rows = [json.loads(line) for line in args.trace.read_text().splitlines() if line]
    result = measure(context, rows)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
