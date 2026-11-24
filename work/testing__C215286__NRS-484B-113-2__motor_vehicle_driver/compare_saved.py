"""Independent physical comparison of two sealed reverse-crosswalk attempts.

The inputs are original saved frame streams and reviewed source packets. This
reports measured geometry only; it does not classify legal compliance.
"""

import argparse
import json
from pathlib import Path

from analyze_source import load_measured
from crosswalk_delivery import audit, compare


PAIRS = {
    "reverse_contact_vs_clear": ("disjoint", "contact"),
    "reverse_overlap_vs_clear": ("disjoint", "overlap"),
}


def compare_attempts(left_attempt, right_attempt, *, comparison_id):
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact comparison")
    if Path(left_attempt).resolve() == Path(right_attempt).resolve():
        raise ValueError("distinct saved attempts required")
    left_source, left, left_hash = load_measured(left_attempt)
    right_source, right, right_hash = load_measured(right_attempt)
    left_target, right_target = PAIRS[comparison_id]
    for key in ("map_name", "map_sha256", "crosswalk_source",
                "crosswalk_polygon_xy", "vehicle_blueprint_id", "driver_source",
                "district_source"):
        if left_source["map_packet"][key] != right_source["map_packet"][key]:
            raise ValueError("fixed source differs: " + key)
    if left["vehicle_actor_id"] != right["vehicle_actor_id"]:
        raise ValueError("fixed vehicle actor identity differs")
    if [r["time_s"] for r in left["frames"]] != [r["time_s"] for r in right["frames"]]:
        raise ValueError("comparison original times differ")
    audit(left, expected_relation=left_target)
    audit(right, expected_relation=right_target)
    physical = compare(left, right, changed_target=right_target)
    return {"comparison_id": comparison_id, "physical_comparison": physical,
            "original_frame_sha256": [left_hash, right_hash],
            "fixed_source_fields": ["map_name", "map_sha256", "crosswalk_source",
                                    "crosswalk_polygon_xy", "vehicle_blueprint_id",
                                    "driver_source", "district_source", "vehicle_actor_id",
                                    "frame_window", "time_window"],
            "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-attempt", required=True)
    parser.add_argument("--right-attempt", required=True)
    parser.add_argument("--comparison-id", choices=tuple(PAIRS), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = compare_attempts(args.left_attempt, args.right_attempt,
                              comparison_id=args.comparison_id)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
