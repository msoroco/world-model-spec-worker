"""Recheck five saved primaries and reject a missing original notice source."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from overtaken_delivery_audit import audit

LABELS = {"audible": "audible", "observed": "observed", "no-right": "no-right",
          "speed": "speed-increase", "right-pass": "right-pass"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(package, attempt_root):
    results = {}
    for label, attempt_name in LABELS.items():
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
    parser.add_argument("--output")
    parser.add_argument("--case")
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    if args.case:
        matches = [(label, attempt_name, package / f"{label}-primary-saved-processing.json")
                   for label, attempt_name in LABELS.items()
                   if json.loads((package / f"{label}-primary-saved-processing.json").read_text())["case_id"] == args.case]
        if len(matches) != 1:
            raise ValueError("Unknown exact case: " + args.case)
        label, attempt_name, receipt = matches[0]
        attempt = Path(args.attempt_root) / attempt_name
        if args.negative:
            missing_name = "overtaken_source.jsonl" if label == "observed" else "signal_command_original.jsonl"
            with tempfile.TemporaryDirectory(prefix="c179789-delivery-") as directory:
                incomplete = Path(directory)
                for item in attempt.iterdir():
                    if item.name != missing_name:
                        (incomplete / item.name).symlink_to(item.resolve())
                audit(incomplete, receipt)
            raise ValueError("Missing original source was accepted")
        print(json.dumps(audit(attempt, receipt), allow_nan=False))
        return
    if not args.output or args.negative:
        raise ValueError("Aggregate proof requires --output and no --negative")
    result = prove(package, Path(args.attempt_root))
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print("five saved-source delivery positives and five missing-original negatives pass")


if __name__ == "__main__":
    main()
