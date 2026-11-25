"""Check synthetic physical outcomes without asserting Native realization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from native_construction import ASSIGNMENT


def check(path, case, expected):
    result = json.loads(Path(path).read_text())
    if result.get("case_id") != case or not case.startswith(ASSIGNMENT + "__"):
        raise ValueError("synthetic physical fixture exact case differs")
    if result.get("provenance_kind") != "synthetic_fixture" or result.get("diagnostic_fixture") is not True:
        raise ValueError("synthetic physical fixture provenance missing")
    if result.get("legal_acceptance_claimed") is not False or result.get("physical_acceptance_claimed") is not False:
        raise ValueError("synthetic fixture asserts legal or physical acceptance")
    maneuver = result.get("physical_checks", {}).get("maneuver", {})
    if maneuver.get("status") != expected or not maneuver.get("method") or not maneuver.get("sources"):
        raise ValueError("synthetic physical outcome differs")
    if result.get("maneuver_completed") != (expected == "met"):
        raise ValueError("synthetic physical completion boolean differs")
    if expected == "met" and not result.get("realized_observables"):
        raise ValueError("synthetic completion measurement missing")
    return {"case_id": case, "status": expected, "passed": True,
            "diagnostic_fixture": True}


def check_lifecycle(path):
    events = json.loads(Path(path).read_text())["events"]
    expected = ["capture_finished", "encoders_closed", "restoration_verified",
                "native_exit", "owner_released", "saved_processing_started"]
    if events != expected:
        raise ValueError("saved processing began before Native owner release")
    return {"events": events, "passed": True, "diagnostic_fixture": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--result")
    parser.add_argument("--case")
    parser.add_argument("--expected", choices=("met", "not_met", "unverified"))
    parser.add_argument("--lifecycle")
    args = parser.parse_args()
    if args.lifecycle:
        print(json.dumps(check_lifecycle(args.lifecycle), sort_keys=True))
    else:
        print(json.dumps(check(args.result, args.case, args.expected), sort_keys=True))


if __name__ == "__main__":
    main()
