"""Independent fixed-source checks for the three center-lane comparisons."""
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
        raise ValueError("exact center-lane comparison identity differs")
    if len(attempts) != len(row["case_ids"]):
        raise ValueError("comparison member count differs")
    observed = [measure(attempt) for attempt in attempts]
    if [item[0] for item in observed] != row["case_ids"]:
        raise ValueError("comparison member order differs")
    sites = [item[3] for item in observed]
    measured = [item[1] for item in observed]
    base = (sites[0]["highway_road_id"], sites[0]["lanes"],
            sites[0]["driver_id"], sites[0]["ego_blueprint_id"],
            sites[0]["road_sha256"])
    if any((site["highway_road_id"], site["lanes"], site["driver_id"],
            site["ego_blueprint_id"], site["road_sha256"]) != base
           for site in sites[1:]):
        raise ValueError("fixed highway, lane or actor source context differs")
    if any(not item["center_lane_occupancy_frames"] or
           item["purpose_sufficiency"] != "unresolved" or
           item["legal_judgment"] is not None for item in measured):
        raise ValueError("source observation or unresolved judgment differs")
    if comparison == "qualifying_turn_directions":
        if [item["route_relationship"] for item in measured] != \
                ["from_highway", "onto_highway"] or \
                [item["declared_purpose"] for item in measured] != \
                ["left_turn_from_highway", "left_turn_onto_highway"] or \
                any(not item["observed_left_turn_frames"] for item in measured):
            raise ValueError("two left-turn route directions not observed")
    elif comparison == "purpose_vs_trajectory":
        if [item["declared_purpose"] for item in measured] != \
                ["left_turn_from_highway", "through_travel", "right_turn"] or \
                not measured[0]["observed_left_turn_frames"] or \
                not measured[2]["observed_right_turn_frames"]:
            raise ValueError("purpose and trajectory contrast differs")
    elif comparison == "intersection_classification":
        if [item["junction_kind"] for item in measured] != \
                ["street_intersection", "alley"] or \
                [item["intersection_eligible"] for item in measured] != [True, False]:
            raise ValueError("street/alley source distinction differs")
    else:
        raise ValueError("unknown center-lane comparison")
    return {"format": "c382162-independent-center-lane-comparison-audit-v1",
            "assignment_id": ASSIGNMENT, "comparison_id": comparison,
            "case_ids": row["case_ids"], "site_source_sha256": [
                sha(Path(attempt) / "native/site.json") for attempt in attempts],
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
