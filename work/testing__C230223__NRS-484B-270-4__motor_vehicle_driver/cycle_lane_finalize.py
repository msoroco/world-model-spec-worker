"""CLI for saved-only original delivery and four-case comparison audits.

The caller supplies source hashes reviewed outside this package. Output is
written only after source, frame, and media checks pass.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cycle_lane_comparison import audit_pairs
from cycle_lane_delivery import audit_delivery


def run(review_path: str | Path, output_path: str | Path) -> dict:
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    attempts, hashes = review.get("attempts"), review.get("reviews")
    if not isinstance(attempts, dict) or not isinstance(hashes, dict):
        raise ValueError("four attempt paths and independent review hashes required")
    comparison = audit_pairs(attempts, hashes)
    deliveries = {}
    for case_id, attempt in attempts.items():
        selected = hashes[case_id]
        deliveries[case_id] = audit_delivery(attempt, selected["site"],
                                              selected["subsection_3"],
                                              selected["vehicle"])
    result = {"format": "cycle-lane-saved-finalization-v1",
              "assignment_id": comparison["assignment_id"],
              "comparisons": comparison["comparisons"],
              "deliveries": deliveries,
              "physical_acceptance_claimed": False, "legal_verdict": None}
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True,
                        help="JSON containing four attempt paths and independently reviewed source hashes")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = run(args.review, args.output)
    print(json.dumps({"format": report["format"],
                      "case_count": len(report["deliveries"]),
                      "comparison_count": len(report["comparisons"]),
                      "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
