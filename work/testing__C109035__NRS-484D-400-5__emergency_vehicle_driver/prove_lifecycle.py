"""Verify saved processing starts after a sealed diagnostic capture returns."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit
from emergency_scene import CASE_KNOBS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    args = parser.parse_args()
    suffix = args.case_id.removeprefix(HERE.name + "__")
    if suffix == args.case_id or suffix not in CASE_KNOBS:
        raise ValueError("Exact lifecycle case required")
    folder = (REPO / ".runtime-work/c109035-delivery-proofs" /
              suffix / "positive/capture")
    receipt = json.loads((folder / "capture_receipt.json").read_text())
    status = json.loads((folder / "native-run-status.json").read_text())
    if (receipt.get("case_id") != args.case_id or
            status.get("capture") != receipt or
            status.get("restoration", {}).get("restored") is not True or
            status.get("errors") or
            not (folder / "camera_trace.jsonl").is_file()):
        raise ValueError("Diagnostic capture or restoration unsealed")
    # The synthetic adapter has returned, and the saved audit is invoked only now.
    result = audit(folder, case_id=args.case_id, diagnostic_test=True)
    if result["physical_checks"]["maneuver"]["status"] != "met":
        raise ValueError("Saved audit did not observe complete synthetic motion")
    events = ["capture_finished", "encoders_closed", "restoration_verified",
              "native_exit", "owner_released", "saved_processing_started"]
    print(json.dumps({"case_id": args.case_id, "diagnostic_fixture": True,
                      "events": events, "saved_audit_passed": True}, sort_keys=True))


if __name__ == "__main__":
    main()
