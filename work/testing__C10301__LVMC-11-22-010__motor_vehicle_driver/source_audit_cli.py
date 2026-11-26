"""Reopen one original alley attempt for independent saved-source auditing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from saved_delivery import CASE_PROFILES, audit


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=sorted(CASE_PROFILES))
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("source audit receipt already exists")
    receipt = audit(args.attempt, args.case, require_delivery=True)
    if receipt.get("diagnostic_fixture") is not False:
        raise ValueError("diagnostic source cannot qualify for delivery")
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": args.case, "decoded_original_pngs":
                      receipt["decoded_original_pngs"], "source_audit_passed": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
