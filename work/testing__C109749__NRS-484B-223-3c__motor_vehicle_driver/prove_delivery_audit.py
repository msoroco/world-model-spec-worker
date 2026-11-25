"""Independent source audit over one exact saved diagnostic attempt.

The negative mode enforces the production full-original-PNG boundary. Neither
mode claims physical acceptance or a legal result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit_saved_delivery
from saved_finalizer import finalize_saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--mode", choices=("diagnostic-positive", "production-negative"), required=True)
    args = parser.parse_args()
    root = args.attempt.resolve()
    if not root.is_dir() or root.name != "original-attempt":
        raise ValueError("Original attempt directory required")
    receipt_path = root / "native/capture-receipt.json"
    receipt = json.loads(receipt_path.read_text())
    if receipt["case_id"] != args.case:
        raise ValueError("Delivery audit selects another exact case")
    if args.mode == "diagnostic-positive":
        marker = json.loads((root.parent / "fixture-provenance.json").read_text())
        if marker.get("diagnostic_fixture") is not True:
            raise ValueError("Diagnostic source provenance required")
        audited = audit_saved_delivery(root, receipt)
        if audited["verified_frame_count"] != 900:
            raise ValueError("Diagnostic audit needs 900 original source frames")
        print(json.dumps({"case_id": args.case, "verified_frame_count": 900,
                          "censored": audited["measured"]["censored"],
                          "scope": "synthetic diagnostic source join only",
                          "physical_acceptance_claimed": False,
                          "legal_judgment": None}))
    else:
        # Production delivery must decode 3,600 original PNGs. The text-only
        # diagnostic deliberately cannot meet that requirement.
        finalize_saved(root, args.case, 900)
        raise ValueError("Diagnostic source unexpectedly satisfied production delivery audit")


if __name__ == "__main__":
    main()
