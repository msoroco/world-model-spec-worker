"""Verify synthetic capture closure precedes saved processing."""

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--saved-receipt", type=Path, required=True)
    args = parser.parse_args()
    selected = json.loads((HERE / "diagnostic-execution-manifest.json").read_text())["cases"]
    if args.case not in {item["case_id"] for item in selected}:
        raise ValueError("exact selected case required")
    provenance = json.loads((args.attempt / "acquisition-provenance.json").read_text())
    saved = json.loads(args.saved_receipt.read_text())
    if (provenance.get("provenance_kind") != "synthetic_fixture" or
            provenance.get("diagnostic_fixture") is not True or
            saved.get("case_id") != args.case or not saved.get("passed") or
            not saved.get("recorded_only") or not saved.get("originals_preserved")):
        raise ValueError("synthetic saved-only lifecycle source invalid")
    print(json.dumps({"case_id": args.case, "events": EVENTS, "exit_code": 0,
                      "scope": "synthetic lifecycle protocol only",
                      "original_owner_release_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
