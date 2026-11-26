"""Exact source-gated Native entrypoint for NRS 484B.270(2)(b)."""

import argparse
import importlib
import json
import os
from pathlib import Path

from passing_native_capture import capture


AID = "testing__C272352__NRS-484B-270-2b__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def selected(root):
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    case = config.get("case")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-270-2b", "C272352", "motor_vehicle_driver"):
        raise ValueError("exact law/cell/actor mismatch")
    if not isinstance(case, dict) or config.get("selected_case_id") != case.get("case_id") or \
            not case["case_id"].startswith(AID + "__"):
        raise ValueError("selected exact case mismatch")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("original 900-frame policy changed")
    if tuple(x.get("name") for x in config.get("cameras", [])) != CAMERAS:
        raise ValueError("four-camera original policy changed")
    if case.get("control_kind") not in {"bicycle", "electric_bicycle", "electric_scooter"} or \
            case.get("same_direction_lane_count_requested") != 1:
        raise ValueError("qualifying one-lane control required")
    return config, case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--reviewed-packet", type=Path)
    parser.add_argument("--adapter-module")
    args = parser.parse_args()
    _, case = selected(Path(__file__).resolve().parent)
    if args.check:
        print("exact original passing configuration passed: " + case["case_id"])
        return
    if not args.output_dir or not args.host or not args.port:
        raise ValueError("owned Native output, host and port required")
    packet = args.reviewed_packet or os.environ.get("C272352_REVIEWED_PACKET")
    adapter_name = args.adapter_module or os.environ.get("C272352_NATIVE_ADAPTER_MODULE")
    if not packet or not adapter_name:
        raise ValueError("reviewed Native packet and adapter module required")
    adapter = importlib.import_module(adapter_name).create_adapter(args.host, args.port,
                                                                  case["case_id"])
    capture(adapter, Path(packet), case, args.output_dir)


if __name__ == "__main__":
    main()
