"""Independent source-bound distance and highway-route comparison audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis import measure
from native_capture import ASSIGNMENT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempts, comparison, comparison_id, plan):
    planned = json.loads(Path(plan).read_text())
    row = next((item for item in planned["comparisons"]
                if item["comparison_id"] == comparison), None)
    if row is None or comparison_id != ASSIGNMENT + "__" + comparison:
        raise ValueError("exact distance comparison identity differs")
    if len(attempts) != len(row["case_ids"]):
        raise ValueError("comparison member count differs")
    observed = [measure(attempt) for attempt in attempts]
    if [item[0] for item in observed] != row["case_ids"]:
        raise ValueError("comparison member order differs")
    sites = [item[3] for item in observed]
    measured = [item[1] for item in observed]
    fixed = [(site["highway_road_id"], site["lanes"], site["driver_id"],
              site["ego_blueprint_id"], site["road_sha256"], site["junction"])
             for site in sites]
    if any(item != fixed[0] for item in fixed[1:]):
        raise ValueError("fixed highway, lane, junction or actor source context differs")
    if any(item["legal_judgment"] is not None or
           item["body_occupancy_source"] !=
           "original eight-vertex footprint against reviewed lane polygon"
           for item in measured):
        raise ValueError("original body source or unresolved judgment differs")
    if comparison == "below_at_above_200_feet":
        feet = [item.get("observed_center_lane_path_ft") for item in measured]
        if ([item["exact_case_kind"] for item in measured] !=
                ["short_travel", "boundary_travel", "long_travel"] or
                [site["route"]["relationship"] for site in sites] !=
                ["from_highway"] * 3 or
                [item["distance_restriction_applicable"] for item in measured] !=
                [True] * 3 or
                any(type(value) not in (int, float) for value in feet) or
                not (feet[0] < 200 and abs(feet[1] - 200) < 1e-6 and feet[2] > 200) or
                [item["boundary_relation_observed"] for item in measured] !=
                ["below", "at", "above"]):
            raise ValueError("original measured distance boundary sweep differs")
    elif comparison == "from_versus_onto_highway":
        if ([item["exact_case_kind"] for item in measured] !=
                ["long_travel", "onto_highway_contrast"] or
                [site["route"]["relationship"] for site in sites] !=
                ["from_highway", "onto_highway"] or
                [item["distance_restriction_applicable"] for item in measured] !=
                [True, False] or
                measured[0].get("observed_center_lane_path_ft", 0) <= 200 or
                measured[1].get("observed_turn_onto_highway") is not True):
            raise ValueError("original from-versus-onto route relation differs")
    else:
        raise ValueError("unknown center-lane distance comparison")
    return {"format": "c382162-223-3b-independent-distance-comparison-audit-v1",
            "assignment_id": ASSIGNMENT, "comparison_id": comparison,
            "case_ids": row["case_ids"],
            "site_source_sha256": [sha(Path(attempt) / "native/site.json")
                                   for attempt in attempts],
            "measured": measured, "fixed_context_checked": True,
            "deliberate_difference_checked": True,
            "diagnostic_fixture": all(item[4] for item in observed),
            "physical_acceptance": False, "legal_judgment": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite independent comparison audit")
    value = audit(args.attempt, args.comparison, args.comparison_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
