"""Measure original motor-vehicle occupancy of a documented trail corridor."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "ego_front", "barrier", "trail_side"}


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def box(value, name):
    if not isinstance(value, dict) or set(value) != {"min_x", "max_x", "min_y", "max_y"}:
        raise ValueError(f"Missing {name} bounds")
    result = {key: number(item, f"{name}.{key}") for key, item in value.items()}
    if result["min_x"] >= result["max_x"] or result["min_y"] >= result["max_y"]:
        raise ValueError(f"Invalid {name} bounds")
    return result


def overlap(a, b):
    return min(a["max_x"], b["max_x"]) > max(a["min_x"], b["min_x"]) and min(a["max_y"], b["max_y"]) > max(a["min_y"], b["min_y"])


def measure(context, rows):
    if context.get("source_kind") != "native_trail_map_and_document_readback":
        raise ValueError("Missing Native trail and document readback")
    for key in ("native_map_sha256", "designation_document_sha256", "dedication_document_sha256",
                "posted_sign_pixel_sha256", "vehicle_identity_sha256"):
        value = context.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"Missing source hash: {key}")
    if context.get("official_designation") != "nonmotorized_trail":
        raise ValueError("Official trail designation not established")
    if context.get("city_dedication") is not True:
        raise ValueError("City dedication not established")
    if context.get("posted_prohibition") is not True:
        raise ValueError("Posted prohibition not established")
    if context.get("vehicle_class") != "motorized_vehicle":
        raise ValueError("Motorized vehicle identity not established")
    exception_kind = context.get("exception_kind")
    if exception_kind not in ("none", "emergency_vehicle", "right_of_way_maintenance", "mobility_device"):
        raise ValueError("Exception identity not sourced")
    exception_hash = context.get("exception_source_sha256")
    if not isinstance(exception_hash, str) or len(exception_hash) != 64 or any(
            char not in "0123456789abcdef" for char in exception_hash):
        raise ValueError("Exception source hash absent")
    if exception_kind == "right_of_way_maintenance" and context.get("maintenance_of_this_right_of_way") is not True:
        raise ValueError("Maintenance of this right-of-way not sourced")
    if exception_kind == "mobility_device" and not (
            context.get("designed_for_mobility_impairment") is True and
            context.get("used_by_mobility_impaired_person") is True):
        raise ValueError("Mobility-device design and use not sourced")
    corridor = box(context.get("trail_right_of_way_m"), "trail right-of-way")
    gap = number(context.get("barrier_clear_gap_m"), "barrier clear gap")
    width = number(context.get("vehicle_width_m"), "vehicle width")
    if gap <= 0 or width <= 0 or gap < width:
        raise ValueError("Barrier has no sourced vehicle clearance")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    inside = []
    previous_native = None
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("video_frame") != index:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (previous_native is not None and native <= previous_native):
            raise ValueError("Native frame identity gap")
        previous_native = native
        if abs(number(row.get("time_s"), "time") - index / RATE_HZ) > 1e-6:
            raise ValueError("Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[name] != index for name in CAMERAS):
            raise ValueError("Four source camera frame join failed")
        footprint = box(row.get("vehicle_footprint_m"), "vehicle footprint")
        inside.append(overlap(footprint, corridor))
    intervals = []
    start = None
    for index, state in enumerate(inside + [False]):
        if state and start is None:
            start = index
        elif not state and start is not None:
            intervals.append([start, index - 1])
            start = None
    return {"format": "worker-source-trail-occupancy-measurement", "frame_count": FRAMES,
            "rate_hz": RATE_HZ, "occupancy_intervals": intervals,
            "occupancy_frames": sum(inside), "ever_within_right_of_way": any(inside),
            "administrative_prerequisites_source_claimed": True,
            "exception_kind_source_claim": exception_kind,
            "exception_source_sha256": exception_hash,
            "legal_compliance": "unassessed", "physical_source_review": "pending_independent_review",
            "limitations": ["Document and pixel hashes require original independent review",
                            "Exception status and sign appropriateness are not decided by occupancy geometry"]}


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
