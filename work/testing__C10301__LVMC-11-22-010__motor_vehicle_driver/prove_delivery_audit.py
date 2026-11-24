"""Exercise the independent source audit and its diagnostic delivery refusal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from saved_delivery import audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--mode", choices=("diagnostic-positive", "delivery-negative"), required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    if args.case not in (folder.name + "__steady_travel", folder.name + "__steering_variation"):
        raise ValueError("Foreign exact case")
    repo = folder.parents[1]
    if repo / ".runtime-work" not in args.attempt.resolve().parents:
        raise ValueError("Attempt must be under .runtime-work")
    receipt = audit(args.attempt, args.case, require_delivery=args.mode == "delivery-negative")
    if args.mode == "diagnostic-positive":
        if receipt["decoded_original_pngs"] != 3600 or receipt["diagnostic_fixture"] is not True:
            raise ValueError("Diagnostic original-source audit differs")
        print(json.dumps({"case_id": args.case, "source_audit_passed": True,
                          "decoded_original_pngs": receipt["decoded_original_pngs"],
                          "diagnostic_fixture": True, "delivery_accepted": False}))
    else:
        raise ValueError("Diagnostic source was accepted for delivery")


if __name__ == "__main__":
    main()
