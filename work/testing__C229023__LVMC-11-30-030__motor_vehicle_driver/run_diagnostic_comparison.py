"""Run one selected diagnostic comparison against saved source and media."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from diagnostic_comparison_audit import audit


ROOT = Path(__file__).resolve().parent
SCRATCH = Path(__file__).resolve().parents[2] / ".runtime-work" / "lead-nov24-converter"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison_id")
    args = parser.parse_args()
    plan = json.loads((ROOT / "case-plan.json").read_text())
    pairs = {row["comparison_id"]: row["case_ids"] for row in plan["comparisons"]}
    case_ids = pairs[args.comparison_id]
    folders = []
    for case_id in case_ids:
        suffix = case_id.removeprefix(ROOT.name + "__")
        folders.append(SCRATCH / ("unmarked-pass-v4" if suffix == "unmarked_pass" else "compat-" + suffix))
    result = audit(left_dir=folders[0], right_dir=folders[1],
                   comparison_id=args.comparison_id, fixture_mode=True)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
