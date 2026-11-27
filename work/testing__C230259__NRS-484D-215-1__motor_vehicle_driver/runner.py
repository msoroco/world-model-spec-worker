"""Exact source-reviewed Native road-beam entrypoint."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

ASSIGNMENT = "testing__C230259__NRS-484D-215-1__motor_vehicle_driver"


def check() -> dict:
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    raw_plan = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(raw_plan).hexdigest() != config.get("plan_sha256"):
        raise ValueError("exact source-grounded beam plan changed")
    plan = json.loads(raw_plan)
    case_id = config.get("selected_case_id")
    case = config.get("case_plan")
    if (config.get("assignment_id") != ASSIGNMENT or
            config.get("law_id") != "NRS-484D-215-1" or
            config.get("cell_id") != "C230259" or
            config.get("actor") != "motor_vehicle_driver" or
            case_id not in config.get("supported_case_ids", []) or
            not isinstance(case, dict) or case.get("case_id") != case_id or
            case not in plan.get("cases", [])):
        raise ValueError("selected exact road-beam case differs")
    if config.get("rate_hz") != 20 or config.get("frame_count") != 900 or config.get("duration_s") != 45:
        raise ValueError("selected original 20 Hz capture profile differs")
    cameras = config.get("cameras")
    if not isinstance(cameras, list) or [x.get("name") for x in cameras] != [
            "overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("four selected original cameras required")
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    config = check()
    if args.check:
        print("selected road-beam bundle passed: " + config["selected_case_id"])
        return
    packet_path = os.environ.get("BEAM_ROAD_SITE_PACKET")
    if not packet_path or not args.output_dir:
        raise ValueError("BEAM_ROAD_SITE_PACKET and original output directory required")
    from beam_native import capture
    from beam_publication import publish
    from scenario_pipeline.worker_exchange.native_output import physical_result, seal_capture, write_result
    import carla

    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    output = Path(args.output_dir)
    capture(client, Path(packet_path), output, config["case_plan"])
    result = publish(output)
    write_result(output, physical_result(output, result))
    seal_capture(output, frames=900,
                 restoration={"restored": True,
                              "settings_readback": "world_restore.restore returned without error"},
                 errors=[], encoder_exit_codes={name: 0 for name in
                                                 ("overview", "approach", "reference_corner", "driver_reference")},
                 context={"case_id": config["selected_case_id"],
                          "site_sha256": hashlib.sha256((output / "site-packet.json").read_bytes()).hexdigest()})


if __name__ == "__main__":
    main()
