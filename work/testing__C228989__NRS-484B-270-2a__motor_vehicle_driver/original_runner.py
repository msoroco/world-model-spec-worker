"""Source-gated entrypoint for one exact original bicycle/scooter pass."""

import argparse
import importlib
import json
import os
from pathlib import Path

from package_spec import AID, ACTOR, CAMERA_NAMES, CELL, LAW
from pass_native_capture import capture


def selected(root):
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    case = config.get("case")
    if not isinstance(case, dict):
        raise ValueError("exact case configuration required")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (LAW, CELL, ACTOR):
        raise ValueError("exact law/cell/actor mismatch")
    if config.get("selected_case_id") != case.get("case_id") or not case["case_id"].startswith(AID + "__"):
        raise ValueError("selected exact case mismatch")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("900-frame original capture policy changed")
    cameras = config.get("cameras")
    if not isinstance(cameras, list) or tuple(row.get("name") for row in cameras) != CAMERA_NAMES:
        raise ValueError("four-camera original capture policy changed")
    if case.get("control_kind") not in {"bicycle", "electric_bicycle", "electric_scooter"}:
        raise ValueError("qualifying control kind missing")
    if case.get("same_direction_lane_count_requested") not in {1, 2}:
        raise ValueError("surveyed same-direction lane count required")
    if case.get("same_direction_lane_count_requested") == 1:
        if case.get("left_lane_traffic_requested") != "not_applicable" or case.get("ego_maneuver_request") not in {"pass", "follow"}:
            raise ValueError("one-lane branch configuration changed")
    elif case.get("left_lane_traffic_requested") not in {"open", "occupied"} or case.get("ego_maneuver_request") not in {"move_left", "stay"}:
        raise ValueError("two-lane branch configuration changed")
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
    config, case = selected(Path(__file__).resolve().parent)
    if args.check:
        print("exact original pass configuration passed: " + case["case_id"])
        return
    if not args.output_dir or not args.host or not args.port:
        raise ValueError("owned Native output, host and port required")
    packet = args.reviewed_packet or os.environ.get("C228989_REVIEWED_PACKET")
    module_name = args.adapter_module or os.environ.get("C228989_NATIVE_ADAPTER_MODULE") or "pass_carla_adapter"
    if not packet:
        raise ValueError("reviewed original Native packet required")
    os.environ["C228989_REVIEWED_PACKET"] = str(Path(packet).resolve())
    adapter = importlib.import_module(module_name).create_adapter(args.host, args.port,
                                                                   case["case_id"])
    profile = config.get("control_profile", {})
    if not isinstance(profile, dict):
        raise ValueError("physical control profile must be a mapping")
    capture(adapter, Path(packet), case, args.output_dir, control_profile=profile)


if __name__ == "__main__":
    main()
