"""Exercise exact-case independent audit protocol on synthetic source-shaped data."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests"))
from test_audits import AuditTests
from curb_entry import CASES
from delivery_audit import ASSIGNMENT, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--mode", choices=("diagnostic-positive", "delivery-negative"), required=True)
    args = parser.parse_args()
    case = next((item for item in CASES if args.case == ASSIGNMENT + "__" + item.name), None)
    if case is None:
        raise ValueError("exact selected case required")
    fixture = AuditTests("test_five_source_bound_deliveries_and_four_comparisons")
    fixture.setUp()
    try:
        receipt = fixture.attempt(case)
        if args.mode == "delivery-negative":
            receipt["owner_released"] = False
            audit(fixture.root, receipt, fixture.video_probe)
            raise AssertionError("unreleased diagnostic receipt was accepted")
        result = audit(fixture.root, receipt, fixture.video_probe)
        if result["frames_checked"] != 900 or len(result["video_sha256"]) != 4:
            raise ValueError("diagnostic audit omitted frame/video checks")
        print(json.dumps({"case_id": args.case, "scope": "synthetic audit protocol only",
                          "positive_protocol_passed": True, "original_delivery_claimed": False}, sort_keys=True))
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
