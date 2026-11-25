"""Check exact saved analysis reports against the declared comparison pairs.

This checks source bindings and measured differences in diagnostic CPU reports.
Original Native footage and physical completion require later review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from comparison_audit import PAIRS, ComparisonError, audit_pair


ASSIGNMENT = "testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator"
EXTRA_PAIRS = {"two_vs_three_complete_cycles":
               ("two_cycles_failed_detection", "three_cycles",
                "complete_device_cycles_before_entry")}
ALL_PAIRS = {**PAIRS, **EXTRA_PAIRS}


def measured(path: Path, suffix: str) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("format") != "worker-analysis-report" or report.get("analysis_complete") is not True:
        raise ValueError("complete saved analysis report required")
    if report.get("case_id") != ASSIGNMENT + "__" + suffix:
        raise ValueError("saved analysis case identity differs")
    if report.get("physical_acceptance_claimed") or report.get("legal_verdict_claimed"):
        raise ValueError("diagnostic report claims physical or legal acceptance")
    values = report.get("measured_values")
    if not isinstance(values, dict) or values.get("case_suffix") != suffix:
        raise ValueError("saved measured values differ from exact case")
    return values


def audit_two_vs_three(left: dict, right: dict) -> dict:
    fixed = ("map_sha256", "device_sha256", "detector_sha256", "blueprint_sha256")
    for key in fixed:
        if not left.get(key) or left[key] != right.get(key):
            raise ComparisonError("fixed source differs: " + key)
    for row in (left, right):
        if not row.get("source_sha256") or len(row["source_sha256"]) != 4:
            raise ComparisonError("missing original source bindings")
        if not row.get("straight_route_observed") or not isinstance(row.get("entry_frame"), int):
            raise ComparisonError("original straight entry absent")
        if row.get("duration_frames", 0) <= row["entry_frame"]:
            raise ComparisonError("entry outside original trace")
    base = ("prior_stop_observed", "red_held_to_entry", "detector_occupancy_observed",
            "detector_failure_observed", "conflict_at_entry")
    if any(left.get(key) != right.get(key) for key in base):
        raise ComparisonError("undeclared measured difference")
    if (left.get("complete_device_cycles_before_entry"),
            right.get("complete_device_cycles_before_entry")) != (2, 3):
        raise ComparisonError("two-versus-three cycles not measured")
    if not left["prior_stop_observed"] or not left["red_held_to_entry"] or not left["detector_failure_observed"] or left["conflict_at_entry"]:
        raise ComparisonError("reference case prerequisites not evidenced")
    return {"comparison_id": "two_vs_three_complete_cycles",
            "fixed_sources_checked": len(fixed),
            "independent_original_sources_checked": True,
            "physical_acceptance": False, "legal_verdict": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True, choices=sorted(ALL_PAIRS))
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--negative-stale-map", action="store_true")
    args = parser.parse_args()
    left_suffix, right_suffix, _ = ALL_PAIRS[args.comparison]
    left = measured(args.left, left_suffix)
    right = measured(args.right, right_suffix)
    if args.negative_stale_map:
        right["map_sha256"] = "0" * 64
    result = (audit_two_vs_three(left, right)
              if args.comparison in EXTRA_PAIRS
              else audit_pair(args.comparison, left, right))
    result["diagnostic_fixture"] = True
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
