"""Independently audit three controlled signal/stop/priority comparisons."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis import measure
import native_signal as signal


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempts, comparison, comparison_id, plan):
    planned = json.loads(Path(plan).read_text())
    row = next((item for item in planned["comparisons"]
                if item["comparison_id"] == comparison), None)
    if row is None or comparison_id != signal.ASSIGNMENT + "__" + comparison:
        raise ValueError("exact inoperative-signal comparison identity mismatch")
    if len(attempts) != len(row["case_ids"]):
        raise ValueError("signal comparison member count differs")
    observed = [measure(attempt) for attempt in attempts]
    if [item[0] for item in observed] != row["case_ids"]:
        raise ValueError("signal comparison member order/identity differs")
    sites = [item[2] for item in observed]
    measured = [item[1] for item in observed]
    base = {key: value for key, value in sites[0].items()
            if key not in ("case_id", "other_state", "stop_line_m",
                           "near_crosswalk_m", "nearest_view_point_m")}
    for site in sites[1:]:
        candidate = {key: value for key, value in site.items()
                     if key not in ("case_id", "other_state", "stop_line_m",
                                    "near_crosswalk_m", "nearest_view_point_m")}
        if candidate != base:
            raise ValueError("signal comparison fixed source context differs")
    if comparison == "post_stop_vehicle_priority":
        if [site["other_state"] for site in sites] != \
                ["prior_stop", "within", "none"] or \
                [item["priority_vehicle_observed"] for item in measured] != \
                [True, True, False] or \
                len({item["stop_reference"] for item in measured}) != 1:
            raise ValueError("prior-stop/within/none priority contrast differs")
    elif comparison == "stop_reference_hierarchy":
        if [item["stop_reference"] for item in measured] != \
                ["stop_line", "near_crosswalk", "nearest_view_point"] or \
                len({site["other_state"] for site in sites}) != 1:
            raise ValueError("line/crosswalk/view hierarchy contrast differs")
    elif comparison == "stop_position":
        if [item["stopped_at_required_position"] for item in measured] != \
                [True, False] or \
                len({item["stop_reference"] for item in measured}) != 1 or \
                len({site["other_state"] for site in sites}) != 1:
            raise ValueError("at-reference/late-stop contrast differs")
    else:
        raise ValueError("unknown inoperative-signal comparison")
    if any(item["legal_judgment"] is not None or
           item["cautious_proceeding"] is not None for item in measured):
        raise ValueError("comparison inserted legal cautiousness verdict")
    return {"format": "c376646-independent-signal-comparison-audit-v1",
            "assignment_id": signal.ASSIGNMENT, "comparison_id": comparison,
            "case_ids": row["case_ids"],
            "site_source_sha256": [sha(Path(attempt) / "site.json")
                                   for attempt in attempts],
            "observed_stop_frames": [item["stop_original_frame"] for item in measured],
            "observed_priority": [item["priority_vehicle_observed"] for item in measured],
            "fixed_context_checked": True, "deliberate_difference_checked": True,
            "diagnostic_fixture": all(item[5] for item in observed),
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
    result = audit(args.attempt, args.comparison, args.comparison_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
