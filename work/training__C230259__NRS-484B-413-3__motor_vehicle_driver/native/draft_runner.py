"""Check the unselected prior-signal scene/controller contract."""
import argparse
import json
from pathlib import Path


def check(config):
    expected = "training__C230259__NRS-484B-413-3__motor_vehicle_driver__probe_1"
    if config.get("case_id") != expected or config.get("selected_case_id") != expected:
        raise ValueError("wrong exact case")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-413-3", "C230259", "motor_vehicle_driver"):
        raise ValueError("wrong law, cell, or actor")
    if (config.get("rate_hz"), config.get("duration_s"), config.get("duration_frames")) != (20, 30, 600):
        raise ValueError("full 30-second 20 Hz window required")
    cameras = config.get("cameras")
    if not isinstance(cameras, list) or [c.get("name") for c in cameras] != [
            "overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("four named cameras required")
    if any(c.get("fps") != 20 or c.get("width", 0) < 16 or c.get("height", 0) < 16 for c in cameras):
        raise ValueError("camera cadence or size invalid")
    phases = config.get("control_phases")
    if not isinstance(phases, list) or [(p.get("first_frame"), p.get("last_frame")) for p in phases] != [
            (0, 149), (150, 199), (200, 599)]:
        raise ValueError("controller phases do not cover 600 frames")
    if [p.get("signal_request") for p in phases] != ["none", "brake_lamp", "brake_lamp"]:
        raise ValueError("prior warning policy changed")
    if config.get("follower_policy") != "same_lane_behind_source_measured":
        raise ValueError("rear vehicle source policy absent")
    if config.get("physical_verified") is not False or config.get("legal_verdict") is not None:
        raise ValueError("physical or legal claim in draft")
    return {"checked": True, "frames": 600, "fps": 20, "simulation_started": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        raise SystemExit("Draft requires Native route, acquisition, and capture implementation")
    print(json.dumps(check(json.loads(Path("config.json").read_text()))))
