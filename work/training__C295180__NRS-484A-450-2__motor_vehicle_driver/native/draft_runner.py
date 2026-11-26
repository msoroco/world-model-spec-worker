"""Exact stop-line construction contract and lazy local Native entrypoint."""
import argparse
import json
from pathlib import Path


def check(config):
    base = "training__C295180__NRS-484A-450-2__motor_vehicle_driver__selected_ef239a06__condition_"
    cases = {base + "a": "full_stop", base + "b": "rolling"}
    case = config.get("case_id")
    if case not in cases or config.get("selected_case_id") != case:
        raise ValueError("Exact case identity differs")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484A-450-2", "C295180", "motor_vehicle_driver"):
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
    if config.get("stop_policy") != cases[case]:
        raise ValueError("Controlled stop policy differs")
    if config.get("near_crosswalk_present") is not False or config.get("marked_stop_line_x_m") != 0:
        raise ValueError("Applicable stop-line branch differs")
    if config.get("stop_sign_governs") is not True:
        raise ValueError("Governing stop sign absent")
    if config.get("physical_verified") is not False or config.get("legal_verdict") is not None:
        raise ValueError("Physical or legal result claimed")
    from road_source import inspect
    inspect(Path(__file__).resolve().parent / 'authored-road.xodr')
    return {"case_id": case, "frames": 600, "simulation_started": False,
            "native_capture_implemented": True,
            "selected_for_delivery": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text())
    proof = check(config)
    if args.check:
        print(json.dumps(proof, sort_keys=True))
    elif args.output_dir:
        from live_capture import capture
        print(json.dumps(capture(config['case_id'], args.output_dir,
                                 args.host, args.port), sort_keys=True))
    else:
        parser.error('Supply --check or --output-dir')
