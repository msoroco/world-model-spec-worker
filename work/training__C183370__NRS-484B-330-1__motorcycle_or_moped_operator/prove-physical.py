"""CPU diagnostic outcomes for exact flagger response and closure ordering."""

import argparse
import hashlib
import json
from pathlib import Path

from measure_original import measure_core_join


PREFIX = "training__C183370__NRS-484B-330-1__motorcycle_or_moped_operator__probe_"


def motion(case, kind, attempt):
    attempt = Path(attempt)
    rows = [json.loads(line) for line in (attempt / "native-rows.jsonl").read_text().splitlines()]
    if kind == "complete_motion":
        observed = measure_core_join(attempt, case)
        compliant = case.endswith(("__probe_a", "__probe_c"))
        if observed["body_crossed_during_requested_stop"] == compliant:
            raise ValueError("Exact response not realized in complete diagnostic")
        status = "met"
        realized = {"stop_line_cross_frame": {
            "value": observed["first_observed_stop_line_cross_frame"],
            "unit": "Native frame", "source": "native-rows.jsonl"}}
    elif kind == "incomplete_motion":
        rows = [{**row, "motorcycle_xyz_m": rows[0]["motorcycle_xyz_m"],
                 "motorcycle_speed_mps": 0.0} for row in rows]
        status = "not_met"
        realized = {}
    else:
        rows = rows[:-1]
        status = "unverified"
        realized = {}
    source_bytes = (json.dumps(rows, separators=(",", ":"), sort_keys=True) + "\n").encode()
    return {"case_id": case, "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "maneuver_completed": status == "met",
            "physical_checks": {"maneuver": {
                "status": status,
                "method": "20 Hz source-joined motorcycle body, requested signal and stop-line crossing; counterfactual missing/incomplete cases are CPU diagnostics",
                "sources": [{"name": "diagnostic-native-rows", "rows": len(rows),
                             "sha256": hashlib.sha256(source_bytes).hexdigest()}]}},
            "realized_observables": realized, "original_native_observed": False,
            "physical_acceptance": False, "legal_judgment": None}


def lifecycle():
    events = ["capture_finished", "encoders_closed", "restoration_verified",
              "native_exit", "owner_released", "saved_processing_started"]
    required = {"encoders_closed": "capture_finished",
                "restoration_verified": "encoders_closed",
                "native_exit": "restoration_verified",
                "owner_released": "native_exit",
                "saved_processing_started": "owner_released"}
    seen = set()
    for event in events:
        if event in required and required[event] not in seen:
            raise ValueError("Saved processing starts only after ownership closure")
        seen.add(event)
    return {"events": events, "exit_code": 0, "scope": "CPU lifecycle order only"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion",
                                           "missing_evidence", "lifecycle"), required=True)
    args = parser.parse_args()
    if not args.case.startswith(PREFIX) or args.case[-1] not in "abcd":
        raise ValueError("Another exact case selected")
    print(json.dumps(lifecycle() if args.kind == "lifecycle" else
                     motion(args.case, args.kind, args.attempt), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
