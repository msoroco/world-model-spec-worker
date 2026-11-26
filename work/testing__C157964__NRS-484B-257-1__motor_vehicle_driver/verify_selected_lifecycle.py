"""Check selected synthetic capture cleanup before saved-only processing."""

import argparse
import hashlib
import json
from pathlib import Path

from yield_view import require


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--saved-receipt", required=True, type=Path)
    parser.add_argument("--capture-test-log", required=True, type=Path)
    args = parser.parse_args()
    attempt = args.attempt.resolve()
    receipt = json.loads(args.saved_receipt.read_text())
    seal = json.loads((attempt / "seal.json").read_text())
    capture_test = args.capture_test_log.read_text()
    require(seal.get("case_id") and args.case.endswith("__" + seal["case_id"]) and
            seal.get("diagnostic_fixture") is True and seal.get("frame_count") == 900,
            "selected sealed diagnostic capture missing")
    require("Ran 4 tests" in capture_test and capture_test.rstrip().endswith("OK"),
            "capture cleanup and failure-restoration CPU tests missing")
    require(receipt.get("case_id") == args.case and receipt.get("passed") is True and
            receipt.get("recorded_only") is True and
            receipt.get("originals_preserved") is True and
            receipt.get("timestamp_joins", {}).get("passed") is True and
            receipt.get("events", [None])[0] == "saved_processing_started",
            "post-release saved-only proof missing")
    require(receipt.get("original_source_hashes", {}).get("original-attempt/seal.json") ==
            sha(attempt / "seal.json"), "saved processing is not bound to selected seal")
    print(json.dumps({"case_id": args.case,
                      "synthetic_capture_seal_sha256": sha(attempt / "seal.json"),
                      "capture_cleanup_test_log_sha256": sha(args.capture_test_log),
                      "saved_receipt_sha256": sha(args.saved_receipt),
                      "lifecycle": ["capture_finished", "encoders_closed",
                                    "restoration_verified", "native_exit",
                                    "owner_released", "saved_processing_started"],
                      "source_kind": "synthetic_cpu_fixture",
                      "original_physical_capture": "unverified"}, sort_keys=True))


if __name__ == "__main__":
    main()
