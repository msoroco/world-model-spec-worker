"""Independent exact parked-departure comparison command for local review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_comparisons import PAIRS, compare
from parked_construction import ASSIGNMENT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    row = next((item for item in plan["comparisons"]
                if item["comparison_id"] == args.comparison), None)
    if row is None or args.comparison_id != ASSIGNMENT + "__" + args.comparison:
        raise ValueError("exact comparison identity differs")
    if args.comparison not in PAIRS or len(args.attempt) != 2:
        raise ValueError("comparison member count differs")
    members = [ASSIGNMENT + "__" + name for name in PAIRS[args.comparison]]
    if row["case_ids"] != members:
        raise ValueError("comparison plan members differ")
    if args.output.exists():
        raise ValueError("refusing to replace independent comparison audit")
    configs = [json.loads((attempt / "config.json").read_text()) for attempt in args.attempt]
    if any((cfg["duration_s"], cfg["rate_hz"], cfg["cameras"]) !=
           (configs[0]["duration_s"], configs[0]["rate_hz"], configs[0]["cameras"])
           for cfg in configs[1:]):
        raise ValueError("fixed original capture context differs")
    outcome = compare(args.comparison,
                      *(attempt / "original-attempt" for attempt in args.attempt))
    outcome["fixed_capture_context_checked"] = True
    outcome["physical_acceptance"] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
