"""Independent original trace comparison with declared intervention isolation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from highway_scene_construction import ASSIGNMENT, load_case

INTERVENTIONS = ("highway_width_request", "device_request", "activity_request",
                 "parking_location_request")
SOURCE_HASHES = ("dedication_sha256", "public_access_sha256", "person_identity_sha256",
                 "vehicle_identity_sha256")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_packet(value: dict, diagnostic: bool):
    case_id = value.get("case_id")
    case = load_case(case_id)
    paths = {key: Path(value[key]) for key in ("context", "trace", "receipt")}
    if any(not path.is_file() or path.is_symlink() for path in paths.values()):
        raise ValueError("missing independent original comparison source")
    context = json.loads(paths["context"].read_text())
    receipt = json.loads(paths["receipt"].read_text())
    trace = [json.loads(line) for line in paths["trace"].read_text().splitlines()]
    if (context.get("assignment_id") != ASSIGNMENT or context.get("case_id") != case_id or
            receipt.get("case_id") != case_id or receipt.get("context_sha256") != sha(paths["context"]) or
            receipt.get("trace_sha256") != sha(paths["trace"])):
        raise ValueError("comparison source identity or seal mismatch")
    required_frames = 9 if diagnostic else 900
    if len(trace) != required_frames or receipt.get("frame_count") != required_frames:
        raise ValueError("comparison original frame history incomplete")
    for key in INTERVENTIONS:
        if context.get(key) != case[key]:
            raise ValueError("comparison exact intervention differs: " + key)
    for index, row in enumerate(trace):
        if row.get("frame") != index or abs(row.get("time_s", -1) - index / 20) > 0.002:
            raise ValueError("comparison 20 Hz original time join failed")
    return case, context, receipt, trace


def audit(comparison_id: str, left: dict, right: dict, diagnostic: bool = False) -> dict:
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    row = next((item for item in plan["comparisons"] if item["comparison_id"] == comparison_id), None)
    if row is None or row["case_ids"] != [left.get("case_id"), right.get("case_id")]:
        raise ValueError("unknown exact controlled comparison")
    first = load_packet(left, diagnostic)
    second = load_packet(right, diagnostic)
    a, b = first[0], second[0]
    changes = [key for key in INTERVENTIONS if a[key] != b[key]]
    expected = {"stand_narrow_device": "activity_request", "loading_narrow_device": "activity_request",
                "travel_narrow_device": "activity_request", "park_narrow_no_device": "device_request",
                "park_narrow_unofficial_device": "device_request", "park_narrow_outside_extent": "device_request",
                "park_wider_device": "highway_width_request",
                "park_narrow_device_off_highway": "parking_location_request",
                "park_narrow_device_reverse_approach": "parking_location_request"}
    if changes != [expected[comparison_id]]:
        raise ValueError("comparison changed conditions outside declared intervention")
    for key in SOURCE_HASHES:
        if first[1].get(key) != second[1].get(key):
            raise ValueError("comparison fixed original source differs: " + key)
    return {"assignment_id": ASSIGNMENT, "comparison_id": comparison_id,
            "case_ids": row["case_ids"], "fixed_conditions_checked": row["fixed_conditions"],
            "declared_difference_checked": changes, "source_kind": "synthetic_diagnostic_fixture" if diagnostic else "original_native_delivery",
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    left = json.loads(args.left.read_text())
    right = json.loads(args.right.read_text())
    result = audit(args.comparison, left, right, args.diagnostic)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
