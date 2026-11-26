"""Source-gated exact Native capture entry point for the emergency-unit branch."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path

from emergency_construction import CASES, execute
from native_packet import AID, sha, validate_packet

ROOT = Path(__file__).resolve().parent


def check(root=ROOT):
    config = json.loads((Path(root) / "config.json").read_text(encoding="utf-8"))
    case_id = config.get("selected_case_id")
    cases = {AID + "__" + case.suffix: case for case in CASES}
    if case_id not in cases:
        raise ValueError("selected exact emergency-unit case absent")
    if tuple(config.get(key) for key in ("assignment_id", "law_id", "cell_id", "actor")) != (
            AID, "NRS-484B-267-2b", "C405341", "motor_vehicle_driver"):
        raise ValueError("exact assignment identity differs")
    if (config.get("rate_hz"), config.get("duration_s"), config.get("frame_count")) != (20, 45, 900):
        raise ValueError("original capture clock differs")
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--reviewed-packet", default=os.environ.get("C405341_2B_REVIEWED_PACKET"))
    parser.add_argument("--adapter-module", default=os.environ.get("C405341_2B_NATIVE_ADAPTER_MODULE"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default=os.environ.get("CARLA_HOST"))
    parser.add_argument("--port", type=int, default=os.environ.get("CARLA_PORT"))
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("exact emergency-unit bundle passed: " + case_id)
        return
    if not all((args.reviewed_packet, args.adapter_module, args.output_dir,
                args.host, args.port)):
        raise ValueError("reviewed original packet, Native adapter and endpoint required")
    packet = validate_packet(args.reviewed_packet, case_id)
    module_path = Path(args.adapter_module)
    binding = packet.get("native_adapter")
    if (not module_path.is_file() or module_path.is_symlink() or not isinstance(binding, dict)
            or binding.get("sha256") != sha(module_path) or not binding.get("citation")
            or not binding.get("reviewer")):
        raise ValueError("hash-bound original Native adapter required")
    spec = importlib.util.spec_from_file_location("emergency_native_adapter", module_path)
    if spec is None or spec.loader is None:
        raise ValueError("original Native adapter module missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter = module.open_native_adapter(args.host, args.port)
    snapshot = adapter.snapshot_world()
    try:
        case = next(case for case in CASES if case_id.endswith("__" + case.suffix))
        config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        execute(adapter, case, packet["map_source"], packet["actor_source"],
                packet["authority"], config.get("engineering", {}))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        adapter.capture_original(case_id, 900, packet["cameras"], args.output_dir)
    finally:
        try:
            adapter.restore_world(snapshot)
            adapter.verify_restoration(snapshot)
        finally:
            adapter.close()


if __name__ == "__main__":
    main()
