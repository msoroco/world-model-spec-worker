"""Source-gated Native entrypoint for one exact private-way attempt."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

from private_way_construction import ASSIGNMENT, CASES
from native_acquisition import capture


def check(root: Path) -> dict:
    config = json.loads((root / "config.json").read_text())
    plan_bytes = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config.get("plan_sha256"):
        raise ValueError("private-way exact case plan changed")
    plan = json.loads(plan_bytes)
    case_id = config.get("selected_case_id")
    if (config.get("assignment_id") != ASSIGNMENT or
            config.get("law_id") != "NRS-484B-260" or
            config.get("cell_id") != "C228096" or
            config.get("actor") != "motor_vehicle_driver" or
            case_id not in {case["case_id"] for case in plan["cases"]} or
            case_id.removeprefix(ASSIGNMENT + "__") not in CASES):
        raise ValueError("private-way exact identity differs")
    if (config.get("rate_hz"), config.get("frame_count"),
            config.get("duration_s")) != (20, 900, 45):
        raise ValueError("private-way 20 Hz four-view episode differs")
    if {camera.get("name") for camera in config.get("cameras", [])} != {
            "overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("private-way four camera views differ")
    if set(config.get("supported_case_ids", [])) != {
            case["case_id"] for case in plan["cases"]}:
        raise ValueError("private-way supported case set differs")
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--site", "--site-packet", type=Path)
    parser.add_argument("--output", "--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--operator-module", default="native_operator")
    parser.add_argument("--spawn-offset-m", type=float)
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parent
    config = check(root)
    case_id = config["selected_case_id"]
    if arguments.case and arguments.case != case_id:
        raise ValueError("requested case differs from materialized exact bundle")
    if arguments.check:
        print(case_id)
        return
    site = arguments.site or (Path(os.environ["C228096_SITE_PACKET"])
                              if os.environ.get("C228096_SITE_PACKET") else None)
    if site is None or arguments.output is None:
        raise ValueError("reviewed original site packet and attempt output required")
    offset = (arguments.spawn_offset_m if arguments.spawn_offset_m is not None else
              config.get("spawn_offset_m", 0.0))
    module = importlib.import_module(arguments.operator_module)
    operator = module.create(site, case_id, arguments.host, arguments.port)
    attempt = arguments.output
    attempt.mkdir(parents=True, exist_ok=True)
    original = attempt / "original-attempt"
    observed = capture(operator, case_id, original, spawn_offset_m=offset)
    from finalize_native import finalize
    finalize(attempt, observed)
    print(json.dumps({"case_id": case_id, "attempt": str(attempt),
                      "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
