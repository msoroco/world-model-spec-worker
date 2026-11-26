"""Check the authored 30-second flashing-red approach contract offline."""
import argparse
import json
from pathlib import Path

from controller import State, command

HERE = Path(__file__).resolve().parent


def check():
    config = json.loads((HERE / "config.json").read_text())
    if config["frames"] != 600 or config["rate_hz"] != 20:
        raise ValueError("Exact 30-second source contract differs")
    if config["cell_id"] != "C111271" or config["law_id"] != "NRS-484B-310-1" or \
            config["actor"] != "motor_vehicle_driver":
        raise ValueError("Frozen assignment identity differs")
    if set(config["camera_sources"]) != {
            "overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("Four source cameras required")
    if len(config.get("supported_case_ids", [])) != 6:
        raise ValueError("Six exact reference/stop cases required")
    if not 0 < config["limit_line_x_m"] < config["crosswalk_near_x_m"] < \
            config["intersection_near_x_m"] < 100:
        raise ValueError("Authored stopping-reference geometry differs")
    for stopping, nonstop_case, reference in (("probe_a", "probe_b", 48.0),
                                              ("crosswalk_stop", "crosswalk_no_stop", 50.0),
                                              ("intersection_stop", "intersection_no_stop", 52.0)):
        stopped = State()
        first = command(stopping, reference - 2, 5.0, reference, False, stopped)
        if first["engineering_phase"] != "pre_reference_stop":
            raise ValueError("Stop controller did not brake before reference")
        for _ in range(30):
            after = command(stopping, reference - 2, 0.0, reference, False, stopped)
        if after["engineering_phase"] != "proceed":
            raise ValueError("Stop controller did not release after hold")
        nonstop = command(nonstop_case, reference - 2, 5.0, reference, False, State())
        if nonstop["engineering_phase"] != "proceed":
            raise ValueError("Nonstop comparison controller differs")
    return {"case_id": config["case_id"], "frames": 600, "rate_hz": 20,
            "source_cameras_planned": 4, "exact_cases_checked": 6,
            "controller_hold_frames_tested": 30,
            "native_executed": False,
            "physical_signal_verified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        raise ValueError("Original Native capture remains to be implemented")
    print(json.dumps(check(), sort_keys=True))


if __name__ == "__main__":
    main()
