"""Offline check for an exact but unselected roundabout entry request."""
import argparse
import json
import math
from pathlib import Path


def check(config):
    assignment = "training__C239014__LVMC-11-43-010-B__motor_vehicle_driver"
    case_ids = {assignment + "__selected_a60a4f45__condition_a": 17.0,
                assignment + "__selected_a60a4f45__condition_b": 12.5}
    case_id = config.get("case_id")
    if case_id not in case_ids or config.get("selected_case_id") != case_id:
        raise ValueError("Exact case identity differs")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "LVMC-11-43-010-B", "C239014", "motor_vehicle_driver"):
        raise ValueError("Law/cell/actor identity differs")
    if (config.get("rate_hz"), config.get("duration_s"),
            config.get("duration_frames")) != (20, 30, 600):
        raise ValueError("Full 30-second source window required")
    if [c.get("name") for c in config.get("cameras", [])] != [
            "overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("Four source cameras required")
    if any(c.get("fps") != 20 or c.get("width", 0) < 16 or
           c.get("height", 0) < 16 for c in config["cameras"]):
        raise ValueError("Camera cadence or dimensions differ")
    if config.get("entry_release_s") != case_ids[case_id]:
        raise ValueError("Controlled entry release differs")
    if config.get("lead_conflict_s") != 12 or config.get("follower_conflict_s") != 24:
        raise ValueError("Circulating traffic schedule differs")
    if config.get("physical_verified") is not False or config.get("legal_verdict") is not None:
        raise ValueError("Diagnostic must not claim physical or legal result")
    # The request must be continuous at approach, wait, and entry transitions.
    entry = config["entry_release_s"]
    for t in (6.95, 7.0, entry - 0.05, entry):
        if not math.isfinite(t):
            raise ValueError("Nonfinite request time")
    return {"case_id": case_id, "frames": 600, "duration_s": 30,
            "simulation_started": False, "selected_for_delivery": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        raise SystemExit("Native capture and saved processing are not yet implemented")
    print(json.dumps(check(json.loads(Path("config.json").read_text())), sort_keys=True))
