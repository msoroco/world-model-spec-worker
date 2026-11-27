"""Independent original-frame contrasts for exact private-way pairs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_original_attempt import audit, read
from private_way_construction import ASSIGNMENT


def compare(plan_path, comparison_id, attempts):
    plan = read(Path(plan_path))
    row = next((item for item in plan["comparisons"]
                if item["comparison_id"] == comparison_id), None)
    if row is None or len(attempts) != 2:
        raise ValueError("exact comparison identity or members differ")
    cases = [next(item for item in plan["cases"] if item["case_id"] == cid)
             for cid in row["case_ids"]]
    roots = [Path(path) for path in attempts]
    configs = [read(path / "config.json") for path in roots]
    for cid, config in zip(row["case_ids"], configs):
        if config.get("selected_case_id") != cid:
            raise ValueError("original comparison case identity differs")
    if any((config["duration_s"], config["rate_hz"], config["cameras"]) !=
           (configs[0]["duration_s"], configs[0]["rate_hz"], configs[0]["cameras"])
           for config in configs[1:]):
        raise ValueError("fixed original capture context differs")
    findings = [audit(path / "original-attempt", cid)
                for path, cid in zip(roots, row["case_ids"])]
    sites = [read(path / "original-attempt/site.json") for path in roots]
    source_hashes = [site["sources"] for site in sites]
    if source_hashes[0] != source_hashes[1]:
        raise ValueError("fixed reviewed private-way/highway sources differ")
    for key in ("reviewed_assertions", "private_way_polygon", "highway_polygon",
                "connection_xy", "highway_axis_xy", "approaches"):
        if sites[0].get(key) != sites[1].get(key):
            raise ValueError("fixed reviewed site condition differs: " + key)
    variables = [case["draft_variables"] for case in cases]
    actual = [{"maneuver": config["maneuver"],
               "approach_sides": sorted(finding["highway_actor_ids"]),
               "ego_control_policy": config["requested_control_policy"]}
              for config, finding in zip(configs, findings)]
    for index in (0, 1):
        for key in actual[index]:
            value = sorted(variables[index][key]) if key == "approach_sides" else variables[index][key]
            if actual[index][key] != value:
                raise ValueError("original declared comparison variable differs: " + key)
    first_frames = [finding["first_highway_frame"] for finding in findings]
    if comparison_id in ("right_wait_vs_intrude", "left_wait_vs_intrude",
                         "cross_wait_vs_intrude", "both_wait_vs_yield_one"):
        if (actual[0]["maneuver"], actual[0]["approach_sides"]) != \
                (actual[1]["maneuver"], actual[1]["approach_sides"]) or \
                actual[0]["ego_control_policy"] != "yield_all" or \
                first_frames[0] <= first_frames[1]:
            raise ValueError("original waited versus early-entry contrast absent")
    elif comparison_id == "right_approach_vs_none":
        if (actual[0]["approach_sides"], actual[1]["approach_sides"]) != (["right"], []) or \
                actual[0]["ego_control_policy"] != actual[1]["ego_control_policy"] or \
                first_frames[0] != first_frames[1]:
            raise ValueError("original highway-actor presence contrast absent")
    elif comparison_id == "entry_vs_crossing":
        if (actual[0]["maneuver"], actual[1]["maneuver"]) != ("enter", "cross") or \
                actual[0]["approach_sides"] != actual[1]["approach_sides"] or \
                first_frames[0] != first_frames[1]:
            raise ValueError("original entry/crossing contrast absent")
    else:
        raise ValueError("unknown private-way comparison")
    return {"comparison_id": comparison_id, "case_ids": row["case_ids"],
            "first_highway_frames": first_frames,
            "actual_variables": actual,
            "fixed_site_sources_sha256": {key: value["sha256"] for key, value in source_hashes[0].items()},
            "deliberate_contrast": "observed", "structural_status": "passed",
            "physical_acceptance": False, "legal_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--attempt", required=True, type=Path, action="append")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.comparison_id != ASSIGNMENT + "__" + args.comparison:
        raise ValueError("exact comparison identifier differs")
    if args.output.exists():
        raise ValueError("refusing to replace independent comparison audit")
    outcome = compare(args.plan, args.comparison, args.attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n")
