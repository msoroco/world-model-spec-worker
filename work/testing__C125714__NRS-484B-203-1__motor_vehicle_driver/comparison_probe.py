"""Exercise each saved comparison and its missing-difference rejection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from comparison_audit import PAIRS, check

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SAVED = REPO / ".runtime-work" / "c125714-2031" / "delivery-probe"
SCRATCH = REPO / ".runtime-work" / "c125714-2031" / "comparison-probe"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True, choices=PAIRS)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    base = SAVED / "right_half" / "positive" / "attempt"
    other = SAVED / PAIRS[args.comparison] / "positive" / "attempt"
    if args.negative:
        root = SCRATCH / args.comparison
        if root.exists():
            shutil.rmtree(root)
        shutil.copytree(other, root)
        other = root
        report_path = other / "analysis-report.json"
        report = json.loads(report_path.read_text())
        value = report["measurements"]["opposing_pass_measurement"]["value"]
        baseline = json.loads((base / "analysis-report.json").read_text())
        base_value = baseline["measurements"]["opposing_pass_measurement"]["value"]
        if args.comparison == "direction_relative_right_side":
            value["right_of_other_all"] = base_value["right_of_other_all"]
        else:
            value["ego_yielded_paved_fraction_min"] = base_value["ego_yielded_paved_fraction_min"]
        report_path.write_text(json.dumps(report, sort_keys=True) + "\n")
    print(json.dumps(check(args.comparison, base, other, diagnostic=True), sort_keys=True))


if __name__ == "__main__":
    main()
