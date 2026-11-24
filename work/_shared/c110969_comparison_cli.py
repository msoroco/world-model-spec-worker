"""Audit an exact C110969 pair from independently reviewed original attempts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ASSIGNMENT = "testing__C110969__NRS-484B-450-1c__motor_vehicle_driver"
PACKAGE = REPO / "work" / ASSIGNMENT
sys.path.insert(0, str(PACKAGE))

from comparison_audit import audit, original_condition_record  # noqa: E402


def compare_originals(comparison_id: str, left_attempt: Path,
                      right_attempt: Path) -> dict:
    plan = json.loads((PACKAGE / "case-plan.json").read_text())
    matches = [item for item in plan["comparisons"]
               if item["comparison_id"] == comparison_id]
    if len(matches) != 1:
        raise ValueError("Exact comparison absent or ambiguous")
    comparison = matches[0]
    left_id, right_id = comparison["case_ids"]
    if not all(case_id.startswith(ASSIGNMENT + "__")
               for case_id in (left_id, right_id)):
        raise ValueError("Comparison case is outside C110969")
    left = original_condition_record(left_attempt, left_id)
    right = original_condition_record(right_attempt, right_id)
    result = audit(comparison, left, right)
    result["original_attempts"] = [str(left_attempt.resolve(strict=True)),
                                   str(right_attempt.resolve(strict=True))]
    result["physical_acceptance_claimed"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left-attempt", required=True, type=Path)
    parser.add_argument("--right-attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = compare_originals(args.comparison, args.left_attempt,
                               args.right_attempt)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"comparison_id": result["comparison_id"],
                      "case_count": len(result["case_ids"]),
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
