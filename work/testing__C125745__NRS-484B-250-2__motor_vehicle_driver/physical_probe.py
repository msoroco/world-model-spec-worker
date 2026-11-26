"""Classify source-shaped intersection entry motion; diagnostic proof only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from entry_timing import measure


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if ".runtime-work" not in str(args.fixture.resolve()):
        raise ValueError("diagnostic fixture must stay under .runtime-work")
    raw = args.fixture.read_bytes()
    packet = json.loads(raw)
    if packet.get("case_id") != args.case or packet.get("diagnostic_fixture") is not True:
        raise ValueError("wrong exact diagnostic fixture")
    source = {"path": str(args.fixture), "sha256": hashlib.sha256(raw).hexdigest()}
    if packet.get("frames") is None:
        status, observations = "unverified", {}
    else:
        try:
            measured = measure(args.fixture, source["sha256"], case_id=args.case,
                               expected_frames=len(packet["frames"]))
            status = "met"
            observations = {"intersection_entry_time_difference_s":
                            measured["intersection_entry_time_difference_s"],
                            "entry_brackets": measured["entry_brackets"]}
        except ValueError as error:
            if "both original intersection entries required" not in str(error):
                raise
            status, observations = "not_met", {}
    result = {"case_id": args.case, "diagnostic_fixture": True,
              "provenance_kind": "synthetic_fixture", "physical_acceptance_claimed": False,
              "physical_checks": {"maneuver": {"status": status,
                                               "method": "first body footprint intersection transition for both actors",
                                               "sources": [source]}},
              "maneuver_completed": status == "met",
              "realized_observables": observations,
              "legal_judgment": "unresolved"}
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": args.case, "status": status,
                      "diagnostic_fixture": True}, sort_keys=True))


if __name__ == "__main__":
    main()
