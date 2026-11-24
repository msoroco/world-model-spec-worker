"""Exercise exact saved source audit and diagnostic delivery refusal on CPU."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from saved_delivery import PREFIX, SUFFIXES, audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--mode", choices=("diagnostic-positive", "delivery-negative"), required=True)
    args = parser.parse_args()
    if args.case not in {PREFIX + suffix for suffix in SUFFIXES}:
        raise ValueError("Foreign exact case")
    root = Path(__file__).resolve().parents[2]
    if root / ".runtime-work" not in args.attempt.resolve().parents:
        raise ValueError("Saved attempt must be under .runtime-work")
    receipt = audit(args.attempt, allow_diagnostic=args.mode == "diagnostic-positive")
    if receipt["case_id"] != args.case:
        raise ValueError("Saved attempt selects another exact case")
    if args.mode == "diagnostic-positive":
        if (receipt["original_frame_count"] != 900 or not receipt["four_camera_receipts"] or
                receipt["native_source"] or receipt["physical_completion"] or
                receipt["legal_necessity"] != "unresolved"):
            raise ValueError("Diagnostic saved source receipt differs")
        print(json.dumps({"case_id": args.case, "source_audit_passed": True,
                          "decoded_original_images": receipt["decoded_original_images"],
                          "delivery_accepted": False}, sort_keys=True))
    else:
        raise ValueError("Diagnostic source was accepted for delivery")


if __name__ == "__main__":
    main()
