"""Independent exact right-curb comparison command for local review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_comparisons import PAIRS, compare
from curb_geometry import ASSIGNMENT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    row = next((item for item in plan["comparisons"] if item["comparison_id"] == args.comparison), None)
    if (row is None or args.comparison not in PAIRS or
            args.comparison_id != ASSIGNMENT + "__" + args.comparison or
            row["case_ids"] != [ASSIGNMENT + "__" + variant for variant in PAIRS[args.comparison]] or
            len(args.attempt) != 2):
        raise ValueError("exact right-curb comparison identity differs")
    if args.output.exists():
        raise ValueError("refusing to replace independent comparison audit")
    result = compare(args.comparison, *args.attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
