"""Recheck five saved primaries and reject a missing original notice source."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from overtaken_delivery_audit import audit


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(package, attempt_root):
    labels = {"audible": "audible", "observed": "observed", "no-right": "no-right",
              "speed": "speed-increase", "right-pass": "right-pass"}
    results = {}
    for label, attempt_name in labels.items():
        receipt = package / f"{label}-primary-saved-processing.json"
        attempt = attempt_root / attempt_name
        positive = audit(attempt, receipt)
        missing_name = ("overtaken_source.jsonl" if label == "observed"
                        else "signal_command_original.jsonl")
        with tempfile.TemporaryDirectory(prefix="c179789-delivery-") as directory:
            incomplete = Path(directory)
            for item in attempt.iterdir():
                if item.name != missing_name:
                    (incomplete / item.name).symlink_to(item.resolve())
            try:
                audit(incomplete, receipt)
            except ValueError as error:
                negative = str(error)
                if negative != "Missing original delivery source: " + missing_name:
                    raise ValueError("Unexpected negative result: " + negative) from error
            else:
                raise ValueError("Missing original source was accepted: " + missing_name)
        results[label] = {"case_id": positive["case_id"], "positive": positive,
                          "negative": {"missing_original_source": missing_name,
                                       "expected_error": negative, "rejected": True},
                          "saved_receipt_sha256": sha(receipt)}
    return {"format": "worker-overtaken-delivery-proof", "audit_sha256":
            sha(package / "overtaken_delivery_audit.py"), "cases": results,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    result = prove(package, Path(args.attempt_root))
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print("five saved-source delivery positives and five missing-original negatives pass")


if __name__ == "__main__":
    main()
