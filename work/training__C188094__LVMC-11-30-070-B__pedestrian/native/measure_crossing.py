"""Source-bound pedestrian roadway-entry and crosswalk-position measurement."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "pedestrian_front", "crosswalk_side", "overpass_context"}


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def rect(value, name):
    if not isinstance(value, dict) or set(value) != {"min_x", "max_x", "min_y", "max_y"}:
        raise ValueError(f"Missing {name} bounds")
    result = {key: finite(item, f"{name}.{key}") for key, item in value.items()}
    if result["min_x"] >= result["max_x"] or result["min_y"] >= result["max_y"]:
        raise ValueError(f"Invalid {name} bounds")
    return result


def inside(point_x, point_y, bounds):
    return bounds["min_x"] <= point_x <= bounds["max_x"] and bounds["min_y"] <= point_y <= bounds["max_y"]


def measure(context, rows):
    if context.get("source_kind") != "native_pedestrian_crossing_and_district_readback":
        raise ValueError("Missing Native crossing and district readback")
    for key in ("native_map_sha256", "crosswalk_survey_sha256", "business_district_evidence_sha256",
                "overpass_geometry_sha256", "pedestrian_identity_sha256"):
        value = context.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"Missing source hash: {key}")
    if context.get("business_district_review") != "source_supported_pending_independent_review":
        raise ValueError("Business district source finding absent")
    roadway = rect(context.get("roadway_bounds_m"), "roadway")
    crosswalks = context.get("crosswalks")
    if not isinstance(crosswalks, list) or not crosswalks:
        raise ValueError("Missing complete marked and unmarked crosswalk survey")
    prepared = []
    for item in crosswalks:
        if not isinstance(item, dict) or item.get("kind") not in {"marked", "unmarked"}:
            raise ValueError("Invalid crosswalk kind")
        prepared.append((item["kind"], rect(item.get("bounds_m"), "crosswalk")))
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    previous_native = None
    entered = []
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
        x = finite(row.get("pedestrian_x_m"), "pedestrian x")
        y = finite(row.get("pedestrian_y_m"), "pedestrian y")
        if row.get("pedestrian_on_overpass_deck") is True:
            raise ValueError("At-grade crossing conflated with overpass deck")
        entered.append(inside(x, y, roadway))
    entries = [i for i in range(1, FRAMES) if entered[i] and not entered[i - 1]]
    if len(entries) != 1:
        raise ValueError("Expected one sourced roadway entry")
    entry = entries[0]
    x, y = rows[entry]["pedestrian_x_m"], rows[entry]["pedestrian_y_m"]
    memberships = [kind for kind, bounds in prepared if inside(x, y, bounds)]
    return {"format": "worker-source-business-district-crossing-measurement",
            "frame_count": FRAMES, "rate_hz": RATE_HZ,
            "roadway_entry_frame": entry,
            "roadway_entry_point_m": {"x": x, "y": y},
            "entry_crosswalk_kinds": memberships,
            "entry_within_any_marked_or_unmarked_crosswalk": bool(memberships),
            "business_district_physical_status": "pending_independent_review",
            "legal_compliance": "unassessed",
            "limitations": ["Crosswalk survey must include all applicable marked and unmarked crossings",
                            "Business-district legal region requires independent source review"]}


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
