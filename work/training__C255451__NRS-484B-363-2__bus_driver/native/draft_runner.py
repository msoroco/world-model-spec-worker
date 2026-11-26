"""Offline contract check for an unselected exact school-zone bus draft."""
import argparse
import json
from pathlib import Path


def check(config):
    assignment = "training__C255451__NRS-484B-363-2__bus_driver"
    cases = {
        "condition_a": (20, "beacon_active"),
        "condition_b": (30, "beacon_active"),
        "at_limit": (25, "beacon_active"),
        "no_school_day": (30, "no_school_day"),
        "half_hour_window": (30, "half_hour_window"),
        "beacon_not_flashing": (30, "beacon_not_flashing"),
        "nonbeacon_sign_active": (30, "nonbeacon_sign_active"),
        "nonbeacon_sign_inactive": (30, "nonbeacon_sign_inactive"),
    }
    cases = {assignment + "__selected_d08892c9__" + name: values
             for name, values in cases.items()}
    case = config.get("case_id")
    if case not in cases or config.get("selected_case_id") != case:
        raise ValueError("Exact case identity differs")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-363-2", "C255451", "bus_driver"):
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
    if (config.get("speed_request_mph"), config.get("planned_context")) != cases[case]:
        raise ValueError("Controlled speed or exception context differs")
    if config.get("zone_start_x_m") != 100 or config.get("zone_end_x_m") != 200:
        raise ValueError("School crossing zone geometry differs")
    if config.get("source_actor_ids") != ["bus", "child_left", "child_right"]:
        raise ValueError("Bus/child source actors differ")
    if config.get("calendar_verified") is not False or config.get("beacon_verified") is not False:
        raise ValueError("Unverified exception context claimed")
    if config.get("physical_verified") is not False or config.get("legal_verdict") is not None:
        raise ValueError("Physical or legal result claimed")
    return {"case_id": case, "frames": 600, "simulation_started": False,
            "selected_for_delivery": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        raise SystemExit("Native capture and saved processing are not yet implemented")
    print(json.dumps(check(json.loads(Path("config.json").read_text())), sort_keys=True))
