"""Independent fixed-context audit of the three C331230 near-side comparisons."""
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
    plan = json.loads(Path(plan).read_text())
    row = next((item for item in plan["comparisons"]
                if item["comparison_id"] == comparison), None)
    if row is None or comparison_id != ASSIGNMENT + "__" + comparison:
        raise ValueError("exact crosswalk comparison identity mismatch")
    if len(attempts) != len(row["case_ids"]):
        raise ValueError("crosswalk comparison member count differs")
    observed = [measure(attempt) for attempt in attempts]
    if [item[0] for item in observed] != row["case_ids"]:
        raise ValueError("crosswalk comparison member order/identity differs")
    sites = [item[3] for item in observed]
    measured = [item[1] for item in observed]
    base = {key: value for key, value in sites[0].items()
            if key not in ("marked", "halt", "crosswalk_marking_source_sha256")}
    for site in sites[1:]:
        candidate = {key: value for key, value in site.items()
                     if key not in ("marked", "halt", "crosswalk_marking_source_sha256")}
        if candidate != base:
            raise ValueError("crosswalk comparison fixed source context differs")
    if comparison in ("marked_crosswalk_cessation", "unmarked_crosswalk_cessation"):
        if sites[0]["marked"] != sites[1]["marked"] or \
                [site["halt"] for site in sites] != [True, False] or \
                [item["stopped_before_entry"] for item in measured] != [True, False]:
            raise ValueError("halt/rolling comparison measurement differs")
    elif comparison == "crosswalk_marking_at_halt":
        if [site["marked"] for site in sites] != [True, False] or \
                [site["halt"] for site in sites] != [True, True] or \
                [item["stopped_before_entry"] for item in measured] != [True, True]:
            raise ValueError("marking comparison measurement differs")
    else:
        raise ValueError("unknown near-side crosswalk comparison")
    for measured_case in measured:
        if measured_case["stop_before_crosswalk_judgment"] is not None:
            raise ValueError("comparison inserted legal stop judgment")
    return {"format": "c331230-independent-near-crosswalk-comparison-audit-v1",
            "assignment_id": ASSIGNMENT, "comparison_id": comparison,
            "case_ids": row["case_ids"],
            "site_source_sha256": [sha(Path(attempt) / "site.json") for attempt in attempts],
            "observed_entry_frames": [item["crosswalk_entry_frame"] for item in measured],
            "observed_pre_entry_cessation": [item["stopped_before_entry"] for item in measured],
            "fixed_context_checked": True, "deliberate_difference_checked": True,
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
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
