"""Verify every selected synthetic attempt is refused as physical delivery."""

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit_original
from yield_view import CASES, require


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "delivery boundary receipt already exists")
    receipts = []
    for case in CASES:
        attempt = args.fixture_root / case.case_id / "original-attempt"
        site = attempt / "reviewed-site-packet.json"
        try:
            audit_original(attempt, args.fixture_root / "absent-review.json", case,
                           expected_site_packet_sha256=digest(site),
                           expected_review_packet_sha256="0" * 64)
        except ValueError as exc:
            require("diagnostic" in str(exc),
                    "selected attempt failed for a reason other than diagnostic custody")
            receipts.append({"case_id": case.case_id,
                             "seal_sha256": digest(attempt / "seal.json"),
                             "site_packet_sha256": digest(site),
                             "rejection": str(exc)})
        else:
            raise ValueError("diagnostic attempt was accepted as physical delivery")
    result = {"format": "c157964-selected-delivery-boundary-v1",
              "source_kind": "synthetic_cpu_fixture",
              "physical_completion": "unverified", "receipts": receipts}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"rejected_diagnostic_cases": len(receipts)}, sort_keys=True))


if __name__ == "__main__":
    main()
