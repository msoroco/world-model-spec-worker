"""Exercise the saved-only owner-release protocol on a synthetic attempt."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--saved-receipt", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    if args.case not in {item["case_id"] for item in plan["cases"]}:
        raise ValueError("exact case required")
    provenance = json.loads((args.attempt / "acquisition-provenance.json").read_text())
    saved = json.loads(args.saved_receipt.read_text())
    if (provenance.get("provenance_kind") != "synthetic_fixture" or
            provenance.get("diagnostic_fixture") is not True or
            saved.get("case_id") != args.case or saved.get("passed") is not True or
            saved.get("recorded_only") is not True or
            saved.get("originals_preserved") is not True):
        raise ValueError("saved-only synthetic lifecycle source invalid")
    print(json.dumps({"case_id": args.case, "events": EVENTS,
                      "scope": "synthetic protocol only",
                      "original_owner_release_claimed": False}))


if __name__ == "__main__":
    main()
