"""Run the source audit for one explicitly named delivery case."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import delivery_audit
import engineering_delivery_audit
from engineering_sweep_station import engineering_station
from reviewed_scene import ASSIGNMENT, VARIANTS


def audit_case(case_id: str, authority_root: Path, receipt: dict) -> dict:
    if receipt.get("case_id") != case_id:
        raise ValueError("receipt case_id does not match requested exact case")
    if case_id in {ASSIGNMENT + "__" + suffix for suffix in VARIANTS}:
        return delivery_audit.audit(authority_root, receipt)
    if engineering_station(case_id) is not None:
        return engineering_delivery_audit.audit(authority_root, receipt)
    raise ValueError("case_id is outside this assignment's supported cases")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.authority_root.resolve()):
        raise ValueError("fresh audit output outside original source root required")
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    result = audit_case(args.case, args.authority_root, receipt)
    if result.get("case_id") != args.case:
        raise ValueError("audit result case_id does not match requested exact case")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
