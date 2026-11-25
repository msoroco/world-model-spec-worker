"""Check one exact median-opening diagnostic bundle."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import median_source
import native_capture


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    raw = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact median-opening case plan changed")
    plan = json.loads(raw)
    case = config["selected_case_id"]
    if case not in {config["assignment_id"] + "__" + suffix for suffix in
                    ("timing_below_training", "timing_inside_training",
                     "timing_above_training", "right_approach_inside")}:
        raise ValueError("Foreign median-opening case")
    matches = [row for row in plan["cases"] if row["case_id"] == case]
    if len(matches) != 1 or plan["cell_id"] != "C125697":
        raise ValueError("Exact median-opening case absent")
    if (config["law_id"] != "NRS-484B-250-2" or
            config["actor"] != "motor_vehicle_driver" or
            config["crossing_kind"] != "median_opening_roadway_crossing" or
            config["governing_signal_state"] != "inoperative"):
        raise ValueError("Statutory crossing or governing signal contract changed")
    if (config["requested_entry_offset_s"] != matches[0]["planned_entry_time_difference_s"] or
            config["ego_approach_side"] != matches[0]["ego_approach_side"]):
        raise ValueError("Exact-case timing or approach request changed")
    if (config["rate_hz"] != 20 or config["frame_count"] != 900 or
            config["duration_s"] != 45 or
            config["cameras"] != ["overview", "approach", "reference_corner", "driver_reference"]):
        raise ValueError("Original source capture contract changed")
    if config["required_sources"] != ["native_trace", "opendrive", "device_inventory",
                                       "highway_identity",
                                       "camera_overview", "camera_approach", "camera_reference_corner",
                                       "camera_driver_reference"]:
        raise ValueError("Original median-opening source contract changed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--packet", default=os.environ.get("C125697_REVIEWED_PACKET"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic median-opening bundle passed: " + case)
        return
    if not args.output_dir or not args.packet:
        raise ValueError("Reviewed original roadway crossing, governing signal and Native sources required")
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    config = json.loads((Path(__file__).resolve().parent / "config.json").read_text())
    print(json.dumps(native_capture.run(
        client.get_world(), carla, args.packet, args.output_dir, case,
        config["requested_entry_offset_s"], config["ego_approach_side"]), sort_keys=True))


if __name__ == "__main__":
    main()
