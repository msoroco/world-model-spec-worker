"""Independent comparison of two saved original bicycle signal attempts.

This accepts only exact selected cases. Each side passes the production saved
source audit before its measured differences are compared; fixture mode is
reserved for exercising the audit on CPU diagnostics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_comparison_receipts import ALL_PAIRS, audit_two_vs_three, measured
from comparison_audit import audit_pair
from delivery_audit import ASSIGNMENT, audit_processed
from original_pixel_audit import audit as audit_original_pixels


def audit(
    comparison: str,
    left_attempt: Path,
    right_attempt: Path,
    left_processed: Path,
    right_processed: Path,
    authority_root: Path | None,
    left_site: Path | None,
    right_site: Path | None,
    left_review: Path | None = None,
    right_review: Path | None = None,
    *,
    diagnostic: bool = False,
) -> dict:
    if comparison not in ALL_PAIRS:
        raise ValueError("unknown exact comparison")
    if left_attempt.resolve() == right_attempt.resolve():
        raise ValueError("comparison cannot reuse one original attempt")
    if left_processed.resolve() == right_processed.resolve():
        raise ValueError("comparison cannot reuse one processed version")
    if not diagnostic and (authority_root is None or left_site is None or right_site is None):
        raise ValueError("both reviewed original site packets and authority root required")
    if not diagnostic and (left_review is None or right_review is None):
        raise ValueError("both independent original pixel reviews required")
    left_suffix, right_suffix, _ = ALL_PAIRS[comparison]
    left_case = ASSIGNMENT + "__" + left_suffix
    right_case = ASSIGNMENT + "__" + right_suffix
    left_receipt = audit_processed(left_attempt, left_processed, left_case, diagnostic,
                                   authority=authority_root, site_file=left_site)
    right_receipt = audit_processed(right_attempt, right_processed, right_case, diagnostic,
                                    authority=authority_root, site_file=right_site)
    if (left_receipt.get("software_checks_passed") is not True or
            right_receipt.get("software_checks_passed") is not True or
            left_receipt.get("diagnostic_fixture") is not diagnostic or
            right_receipt.get("diagnostic_fixture") is not diagnostic):
        raise ValueError("both original saved-source audits must pass in the selected mode")
    pixel_reviews = None
    if not diagnostic:
        pixel_reviews = [
            audit_original_pixels(left_attempt, left_processed, left_case, left_review,
                                  authority=authority_root, site=left_site),
            audit_original_pixels(right_attempt, right_processed, right_case, right_review,
                                  authority=authority_root, site=right_site),
        ]
        if any(item.get("status") != "original_pixels_reviewed" for item in pixel_reviews):
            raise ValueError("both original pixel reviews must pass")
    left = measured(left_processed / "analysis/analysis-report.json", left_suffix)
    right = measured(right_processed / "analysis/analysis-report.json", right_suffix)
    contrast = (audit_two_vs_three(left, right) if comparison == "two_vs_three_complete_cycles"
                else audit_pair(comparison, left, right))
    return {
        "format": "c111125-original-comparison-v1",
        "assignment_id": ASSIGNMENT,
        "comparison_id": comparison,
        "case_ids": [left_case, right_case],
        "left_source_audit": left_receipt,
        "right_source_audit": right_receipt,
        "measured_contrast": contrast,
        "original_pixel_reviews": pixel_reviews,
        "diagnostic_fixture": diagnostic,
        "physical_acceptance": False,
        "legal_verdict": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", required=True, choices=sorted(ALL_PAIRS))
    parser.add_argument("--left-attempt", required=True, type=Path)
    parser.add_argument("--right-attempt", required=True, type=Path)
    parser.add_argument("--left-processed", required=True, type=Path)
    parser.add_argument("--right-processed", required=True, type=Path)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--left-site", type=Path)
    parser.add_argument("--right-site", type=Path)
    parser.add_argument("--left-review", type=Path)
    parser.add_argument("--right-review", type=Path)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = audit(args.comparison, args.left_attempt, args.right_attempt,
                    args.left_processed, args.right_processed, args.authority_root,
                    args.left_site, args.right_site,
                    args.left_review, args.right_review,
                    diagnostic=args.diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"comparison_id": args.comparison, "source_audits_passed": True,
                      "diagnostic_fixture": args.diagnostic}))


if __name__ == "__main__":
    main()
