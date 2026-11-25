"""Source-bound production comparison for two sealed C227824 Native attempts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from comparison_audit import audit_attempts
from delivery_audit import audit as audit_delivery


def audit(left_attempt, right_attempt, comparison_id, plan_path):
    left = audit_delivery(left_attempt)
    right = audit_delivery(right_attempt)
    paired = audit_attempts(left_attempt, right_attempt, comparison_id, plan_path)
    if paired["case_ids"] != [left["case_id"], right["case_id"]]:
        raise ValueError("Native delivery and comparison case identities differ")
    if paired["diagnostic_fixture"]:
        raise ValueError("diagnostic comparison cannot qualify for delivery")
    if not all(item["native_seal_verified"] and item["source_hashes_verified"]
               for item in (left, right)):
        raise ValueError("paired Native source audit incomplete")
    return {"format": "worker-native-comparison-audit",
            "comparison_id": comparison_id, "case_ids": paired["case_ids"],
            "fixed_source_conditions_checked": paired["fixed_source_conditions_checked"],
            "deliberate_difference_checked": paired["deliberate_difference_checked"],
            "source_sha256": paired["source_sha256"],
            "native_delivery_audits_passed": True,
            "diagnostic_fixture": False, "actual_pixels_verified": False,
            "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left-attempt", required=True)
    parser.add_argument("--right-attempt", required=True)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--plan", default=str(Path(__file__).resolve().parent /
                                               "case-plan.json"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = audit(args.left_attempt, args.right_attempt,
                   args.comparison_id, args.plan)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"comparison_id": args.comparison_id,
                      "native_delivery_audits_passed": True,
                      "physical_acceptance_claimed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
