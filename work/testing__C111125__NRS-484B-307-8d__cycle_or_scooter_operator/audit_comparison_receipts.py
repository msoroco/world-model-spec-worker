"""Check exact saved analysis reports against the declared comparison pairs.

This checks source bindings and measured differences in diagnostic CPU reports.
Original Native footage and physical completion require later review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from comparison_audit import PAIRS, audit_pair


ASSIGNMENT = "testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator"


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True, choices=sorted(PAIRS))
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--negative-stale-map", action="store_true")
    args = parser.parse_args()
    left_suffix, right_suffix, _ = PAIRS[args.comparison]
    left = measured(args.left, left_suffix)
    right = measured(args.right, right_suffix)
    if args.negative_stale_map:
        right["map_sha256"] = "0" * 64
    result = audit_pair(args.comparison, left, right)
    result["diagnostic_fixture"] = True
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
