"""Offline and local Native entrypoint for a selected 253 construction bundle.

The offline mode validates the exact plan against an explicit diagnostic map.
A production run requires a reviewed local Native adapter and map survey.
"""

import argparse
import json
import os
from pathlib import Path

from construction import build


def reviewed_map_packet(argument):
    path = argument or os.environ.get("C109749_MAP_PACKET")
    if not path:
        raise ValueError("reviewed original Native map packet required at capture; set C109749_MAP_PACKET")
    packet = json.loads(Path(path).read_text(encoding="utf-8"))
    if packet.get("diagnostic_fixture") or packet.get("reviewed_original_map") is not True:
        raise ValueError("production capture requires a reviewed original Native map packet")
    return path, packet


def check(config, map_packet):
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("wrong fixed 20 Hz, 45 second capture contract")
    if config.get("cameras") != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("wrong pinned four-camera profile")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-253", "C109749", "motor_vehicle_driver"):
        raise ValueError("wrong law/cell/actor identity")
    request = build(config["selected_case_id"], map_packet)
    if request["capture"]["cameras"] != config["cameras"]:
        raise ValueError("construction camera contract differs")
    policy = config.get("controller")
    if request["controller"] != policy:
        raise ValueError("case policy differs from selected construction")
    return request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--map-packet")
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    if args.check:
        packet = json.loads(Path("diagnostic-map.json").read_text(encoding="utf-8"))
        if packet.get("diagnostic_fixture") is not True:
            raise ValueError("offline map fixture must be marked diagnostic")
        request = check(config, packet)
        print(json.dumps({"case_id": request["case_id"], "offline_contract_passed": True,
                          "real_native_map_reviewed": False, "simulation_started": False}))
        return
    map_path, packet = reviewed_map_packet(args.map_packet)
    check(config, packet)
    from native_entrypoint import run_native
    if not args.output_dir:
        raise ValueError("Native attempt output directory required")
    result = run_native("config.json", map_path, args.output_dir,
                        args.host or "127.0.0.1", int(args.port or 2000))
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
