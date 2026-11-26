"""Measure diagnostic passage through a posted portion, without a legal label."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if ".runtime-work" not in str(args.fixture.resolve()):
        raise ValueError("diagnostic fixture must stay under .runtime-work")
    data = json.loads(args.fixture.read_text())
    if data.get("case_id") != args.case or data.get("diagnostic_fixture") is not True:
        raise ValueError("wrong exact physical fixture")
    rows = data.get("motion_history")
    if rows is None:
        status = "unverified"
    elif not isinstance(rows, list) or len(rows) < 3:
        raise ValueError("incomplete diagnostic motion history")
    else:
        if [row.get("frame") for row in rows] != list(range(len(rows))) or any(
                type(row.get("on_highway")) is not bool or
                type(row.get("speed_mps")) not in (int, float) or row["speed_mps"] < 0
                for row in rows):
            raise ValueError("diagnostic posted-speed motion samples missing")
        status = "met" if any(row["on_highway"] and row["speed_mps"] > 0 for row in rows) else "not_met"
    source = {"path": str(args.fixture),
              "sha256": hashlib.sha256(args.fixture.read_bytes()).hexdigest()}
    result = {"case_id": args.case, "diagnostic_fixture": True,
              "provenance_kind": "synthetic_fixture", "physical_acceptance_claimed": False,
              "physical_checks": {"maneuver": {"status": status,
                                               "method": "source-shaped on-highway motion samples",
                                               "sources": [source]}},
              "maneuver_completed": status == "met",
              "realized_observables": {"on_highway_speed_mps": max(
                  row["speed_mps"] for row in rows if row["on_highway"])} if status == "met" else {},
              "legal_judgment": "unresolved"}
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": args.case, "status": status,
                      "diagnostic_fixture": True}, sort_keys=True))


if __name__ == "__main__":
    main()
