"""Audit original source separation and paired physical route isolation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "native"))
from audit_comparison import audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", type=Path, required=True)
    parser.add_argument("--intrusion", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    if args.negative:
        audit(args.intrusion, args.clear)
        raise AssertionError("Reversed comparison was accepted")
    if args.output is None:
        raise ValueError("Missing saved comparison receipt output")
    value = audit(args.clear, args.intrusion)
    if value["case_ids"] != [PACKAGE.name + "__probe_a", PACKAGE.name + "__probe_b"]:
        raise ValueError("Comparison changed exact case identities")
    if value["physical_acceptance_claimed"] or value["legal_verdict_claimed"]:
        raise ValueError("Diagnostic comparison claimed acceptance")
    args.output.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_ids": value["case_ids"],
                      "deliberate_difference": value["deliberate_difference"],
                      "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
