"""Selected saved-attempt delivery audit with explicit diagnostic separation."""

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit as audit_original_delivery


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, case, allow_diagnostic=False, expected_site_sha256=None,
          review_packet=None, expected_review_sha256=None):
    attempt = Path(attempt).resolve()
    result_path = attempt / "result.json"
    report_path = attempt / "analysis-report.json"
    receipt_path = attempt.parent / "processing.json"
    for path in (result_path, report_path, receipt_path):
        if not path.is_file():
            raise ValueError("recorded-only processing source missing: " + path.name)
    result = json.loads(result_path.read_text())
    report = json.loads(report_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    if result.get("case_id") != case or report.get("case_id") != case or \
            receipt.get("case_id") != case:
        raise ValueError("selected case identity mismatch")
    if not receipt.get("passed") or not receipt.get("recorded_only") or \
            not receipt.get("originals_preserved"):
        raise ValueError("recorded-only source preservation unproven")
    source = attempt / "original-attempt/site-packet.json"
    if not source.is_file():
        raise ValueError("selected original source packet missing")
    source_hash = sha(source)
    measurement = report.get("measurements", {}).get("restricted_zone_entrant_observations", {})
    if measurement.get("sources") != {"original-attempt/site-packet.json": source_hash}:
        raise ValueError("selected measurement source binding stale")
    if result.get("diagnostic_fixture"):
        if not allow_diagnostic:
            raise ValueError("synthetic saved source cannot satisfy original delivery")
        packet = json.loads(source.read_text())
        if packet.get("diagnostic_fixture") is not True or \
                measurement.get("value", {}).get("frame_count") != 9:
            raise ValueError("diagnostic source provenance mismatch")
        return {"case_id": case, "recorded_only": True,
                "diagnostic_fixture": True, "source_sha256": source_hash,
                "software_checks_passed": True, "physical_completion": False,
                "legal_status": "unresolved_judgment"}
    if allow_diagnostic:
        raise ValueError("original attempt must use independent reviewer path")
    if not all((expected_site_sha256, review_packet, expected_review_sha256)):
        raise ValueError("independent original review sources required")
    reviewed = audit_original_delivery(attempt, case, expected_site_sha256,
                                       review_packet, expected_review_sha256)
    return {"case_id": case, "recorded_only": True, "diagnostic_fixture": False,
            "source_sha256": source_hash, "physical_completion": reviewed["physical_completion"],
            "review_sha256": reviewed["review_sha256"],
            "legal_status": "unresolved_judgment"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--allow-diagnostic", action="store_true")
    parser.add_argument("--expected-site-sha256")
    parser.add_argument("--review-packet")
    parser.add_argument("--expected-review-sha256")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.allow_diagnostic,
                           args.expected_site_sha256, args.review_packet,
                           args.expected_review_sha256), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
