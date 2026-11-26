"""Audit the three fixed-condition comparisons on selected diagnostic sources.

These receipts prove source custody and comparison logic only. They do not turn
synthetic fixtures into original physical observations.
"""

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import audit_pair
from yield_view import require


PAIRS = {
    "slow_vs_stop": "yield_stop_approaching",
    "through_phase": "yield_slow_occupied",
    "officer_exception": "officer_controlling",
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "comparison receipt already exists")
    root = args.fixture_root.resolve()
    left = root / "yield_slow_approaching" / "original-attempt"
    receipts = []
    for comparison, right_name in PAIRS.items():
        right = root / right_name / "original-attempt"
        left_site = left / "reviewed-site-packet.json"
        right_site = right / "reviewed-site-packet.json"
        report = audit_pair(comparison, left, right, allow_diagnostic=True,
                            expected_site_hashes=(digest(left_site), digest(right_site)))
        require(report["diagnostic_fixture"] is True and
                report["source_integrity"] is True and
                report["physical_difference"] == "unverified", "diagnostic scope differs")
        try:
            audit_pair(comparison, left, left, allow_diagnostic=True)
        except ValueError as exc:
            require("attempt" in str(exc) or "case" in str(exc),
                    "unexpected same-attempt negative result")
            negative = str(exc)
        else:
            raise ValueError("same-attempt comparison was accepted")
        receipts.append({"comparison_id": comparison, "report": report,
                         "left_seal_sha256": digest(left / "seal.json"),
                         "right_seal_sha256": digest(right / "seal.json"),
                         "left_site_packet_sha256": digest(left_site),
                         "right_site_packet_sha256": digest(right_site),
                         "same_attempt_rejection": negative})
    result = {"format": "c157964-selected-diagnostic-comparisons-v1",
              "source_kind": "synthetic_cpu_fixture", "receipts": receipts,
              "physical_completion": "unverified", "legal_judgment": None}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"comparison_ids": list(PAIRS),
                      "positive": len(receipts), "negative": len(receipts),
                      "source_kind": result["source_kind"]}, sort_keys=True))


if __name__ == "__main__":
    main()
