"""Classify source-shaped restricted-zone motion, for CPU fixtures only."""

import argparse
import hashlib
import json
from pathlib import Path


def classify(packet, case):
    if packet.get("case_id") != case or packet.get("diagnostic_fixture") is not True:
        raise ValueError("wrong exact diagnostic fixture")
    rows = packet.get("rows")
    if rows is None:
        return "unverified", {}
    if not isinstance(rows, list) or len(rows) != 9:
        raise ValueError("diagnostic motion frame history incomplete")
    states = {row.get("passenger_boarding_state") for row in rows}
    exchange = sum(bool(row.get("passenger_exchange_active")) for row in rows)
    approach = sum(bool(row.get("entrant_parking_task_active")) and
                   row.get("entrant_station_m", 99) < 10 for row in rows)
    stationary = sum(10 <= row.get("subject_station_m", -1) <= 30 and
                     row.get("subject_speed_mps", 99) < .1 for row in rows)
    if {"approaching", "boarding", "aboard"} <= states and exchange and approach and stationary:
        return "met", {"exchange_frames": exchange, "approach_frames": approach,
                       "subject_zone_dwell_frames": stationary,
                       "entrant_waiting_frames": sum(bool(row.get("entrant_waiting")) for row in rows),
                       "entrant_access_blocked_frames": sum(bool(row.get("entrant_access_blocked"))
                                                           for row in rows)}
    return "not_met", {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if ".runtime-work" not in args.fixture.resolve().parts:
        raise ValueError("diagnostic fixture must stay under .runtime-work")
    packet = json.loads(args.fixture.read_text())
    status, observations = classify(packet, args.case)
    result = {"case_id": args.case, "diagnostic_fixture": True,
              "provenance_kind": "synthetic_fixture", "physical_acceptance_claimed": False,
              "physical_checks": {"maneuver": {"status": status,
                  "method": "source-shaped passenger transition, zone dwell and reserved-purpose approach",
                  "sources": [{"path": str(args.fixture),
                               "sha256": hashlib.sha256(args.fixture.read_bytes()).hexdigest()}]}},
              "maneuver_completed": status == "met", "realized_observables": observations,
              "legal_judgment": "unresolved"}
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": args.case, "status": status,
                      "diagnostic_fixture": True}, sort_keys=True))


if __name__ == "__main__":
    main()
