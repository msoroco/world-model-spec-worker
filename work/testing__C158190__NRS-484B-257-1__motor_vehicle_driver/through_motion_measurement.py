"""Source-bound motion and comparison checks for the selected yield branch.

These observations are engineering evidence. They do not decide whether a
particular through vehicle posed an immediate hazard under NRS 484B.257(1).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from yield_view_measurement import ASSIGNMENT, measure


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite original " + name + " required")
    return float(value)


def inspect_original(path: str | Path) -> dict:
    """Measure all through traffic during the complete original crossing."""
    path = Path(path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    base = measure(path)
    site = packet["site"]
    if site.get("source_kind") != "original_native_readback" or not site.get("source_recording_id"):
        raise ValueError("original Native site readback identity required")
    for key in ("yield_sign_source_sha256", "marking_survey_sha256",
                "through_highway_survey_sha256", "view_ray_source_sha256"):
        digest = site.get(key)
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("source-bound site readback required: " + key)
    frames = packet["frames"]
    crossing = [i for i, frame in enumerate(frames) if frame["ego_within_intersection"]]
    if not crossing or crossing != list(range(crossing[0], crossing[-1] + 1)):
        raise ValueError("contiguous original crossing history required")
    if crossing[-1] == len(frames) - 1:
        raise ValueError("original exit frame required")
    sightings = {}
    for index in crossing:
        frame = frames[index]
        vehicles = frame.get("through_vehicles")
        if not isinstance(vehicles, list) or not vehicles:
            raise ValueError("original through-vehicle motion required at every crossing frame")
        ids = []
        for vehicle in vehicles:
            if not isinstance(vehicle, dict) or not isinstance(vehicle.get("id"), str) or not vehicle["id"]:
                raise ValueError("through-vehicle identity required")
            if vehicle.get("through_highway") is not True:
                raise ValueError("original through-highway status required")
            distance = _number(vehicle.get("distance_to_conflict_m"), "vehicle distance")
            speed = _number(vehicle.get("speed_mps"), "vehicle speed")
            if speed < 0:
                raise ValueError("through-vehicle speed cannot be negative")
            ids.append(vehicle["id"])
            sightings.setdefault(vehicle["id"], []).append((index, distance, speed))
        if len(ids) != len(set(ids)) or set(ids) != set(frame["through_vehicle_ids"]):
            raise ValueError("through-vehicle identity join mismatch")
    base["source"] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    base["site_source_recording_id"] = site["source_recording_id"]
    base["crossing_frame_indices"] = [crossing[0], crossing[-1]]
    base["through_vehicle_motion"] = [
        {"id": vehicle_id, "observed_frame_count": len(rows),
         "minimum_abs_distance_to_conflict_m": min(abs(row[1]) for row in rows),
         "speed_range_mps": [min(row[2] for row in rows), max(row[2] for row in rows)]}
        for vehicle_id, rows in sorted(sightings.items())
    ]
    base["review_limit"] = ("Original measurements preserve the full crossing and through-vehicle motion; "
                            "a reviewer must determine immediate hazard and right of way without an invented numeric cutoff.")
    return base


def compare_original(left: str | Path, right: str | Path, variable: str) -> dict:
    """Reject a comparison that changes more than its declared intervention."""
    if variable not in {"ego_response", "through_traffic_phase"}:
        raise ValueError("unknown controlled comparison variable")
    packets = [json.loads(Path(path).read_text()) for path in (left, right)]
    results = [inspect_original(path) for path in (left, right)]
    if any(packet.get("assignment_id") != ASSIGNMENT for packet in packets):
        raise ValueError("comparison assignment mismatch")
    fixed_keys = ("map_source_sha256", "intersection_id", "ego_route_source_sha256",
                  "camera_plan_sha256", "duration_frames", "yield_sign_source_sha256",
                  "marking_survey_sha256", "through_highway_survey_sha256",
                  "view_ray_source_sha256")
    for key in fixed_keys:
        if packets[0]["site"].get(key) is None or packets[0]["site"].get(key) != packets[1]["site"].get(key):
            raise ValueError("fixed comparison site source differs: " + key)
    if packets[0]["site"].get("planned_" + variable) == packets[1]["site"].get("planned_" + variable):
        raise ValueError("declared comparison intervention does not differ")
    other = "through_traffic_phase" if variable == "ego_response" else "ego_response"
    if packets[0]["site"].get("planned_" + other) != packets[1]["site"].get("planned_" + other):
        raise ValueError("uncontrolled comparison intervention differs")
    return {"assignment_id": ASSIGNMENT, "variable": variable,
            "case_source_sha256": [result["source"]["sha256"] for result in results],
            "measured": results,
            "review_limit": "Engineering isolation and measurements do not establish a legal outcome."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path)
    parser.add_argument("--left", type=Path)
    parser.add_argument("--right", type=Path)
    parser.add_argument("--variable", choices=("ego_response", "through_traffic_phase"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.original and not any((args.left, args.right, args.variable)):
        result = inspect_original(args.original)
    elif not args.original and all((args.left, args.right, args.variable)):
        result = compare_original(args.left, args.right, args.variable)
    else:
        parser.error("choose one original or a left/right comparison with variable")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
