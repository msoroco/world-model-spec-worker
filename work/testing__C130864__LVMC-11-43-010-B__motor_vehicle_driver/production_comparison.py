"""Compare two independently audited original roundabout attempts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from production_delivery import audit_original
from roundabout_comparison_audit import PAIRS, compare
from roundabout_measurements import ASSIGNMENT_ID, measure


def audit_pair(comparison_id: str, first_attempt: Path, second_attempt: Path,
               first_review_ref: dict, second_review_ref: dict) -> dict:
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact roundabout comparison")
    left_root, right_root = Path(first_attempt).resolve(), Path(second_attempt).resolve()
    if left_root == right_root:
        raise ValueError("comparison requires distinct original attempts")
    left_suffix, right_suffix, _ = PAIRS[comparison_id]
    left_case, right_case = (ASSIGNMENT_ID + "__" + suffix
                             for suffix in (left_suffix, right_suffix))
    left = audit_original(left_root, left_case, first_review_ref)
    right = audit_original(right_root, right_case, second_review_ref)
    audits = []
    for root, case_id, delivery in ((left_root, left_case, left),
                                    (right_root, right_case, right)):
        motion = measure(case_id=case_id, map_path=root / "original-map.json",
                         trace_path=root / "original-trace.jsonl",
                         receipt_path=root / "original-receipt.json")
        audits.append({"case_id": case_id,
                       "decoded_images": delivery["decoded_images"],
                       "motion": motion})
    packets = [json.loads((root / "original-map.json").read_text())
               for root in (left_root, right_root)]
    result = compare(comparison_id, *audits, *packets)
    result.update(original_attempts_audited=True,
                  independent_review_sha256=[left["independent_review_sha256"],
                                             right["independent_review_sha256"]],
                  full_encoded_camera_decodes=8,
                  legal_gap_judgment="unresolved",
                  physical_acceptance=False, legal_verdict=None)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--first-attempt", type=Path, required=True)
    parser.add_argument("--second-attempt", type=Path, required=True)
    parser.add_argument("--first-review-ref", type=Path, required=True)
    parser.add_argument("--second-review-ref", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_pair(args.comparison_id, args.first_attempt,
                        args.second_attempt,
                        json.loads(args.first_review_ref.read_text()),
                        json.loads(args.second_review_ref.read_text()))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
