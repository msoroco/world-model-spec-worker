"""Exact projection bundle entry point; original sources are required locally."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path

from projection_capture import capture_original
from projection_construction import CASES
from projection_measurement import ASSIGNMENT
from projection_sources import load_reviewed, validate_native_adapter

ROOT = Path(__file__).resolve().parent


def check(root=ROOT):
    config = json.loads((Path(root) / "config.json").read_text(encoding="utf-8"))
    case_id = config.get("selected_case_id")
    case = next((item for item in CASES if item.case_id == case_id), None)
    if case is None:
        raise ValueError("exact projection case missing")
    if ((config.get("assignment_id"), config.get("law_id"),
         config.get("cell_id"), config.get("actor")) !=
            (ASSIGNMENT, "LVMC-11-52-060", "C150088", "motor_vehicle_driver")):
        raise ValueError("exact projection assignment identity differs")
    if (config.get("rate_hz"), config.get("duration_s"), config.get("frame_count")) != (20, 45, 900):
        raise ValueError("exact projection capture clock differs")
    if config.get("required_atoms") != [] or config.get("source_packets") != []:
        raise ValueError("original source packets must remain explicit")
    if (config.get("requested_projection_m") != case.projection_m or
            config.get("controlling_part") != case.controlling_part):
        raise ValueError("exact physical construction differs")
    if config.get("candidate_id", "primary") not in ("primary", "fallback1"):
        raise ValueError("unknown exact physical candidate")
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--reviewed-packet", default=os.environ.get("C150088_REVIEWED_PACKET"))
    parser.add_argument("--adapter-module", default=os.environ.get("C150088_NATIVE_ADAPTER_MODULE"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default=os.environ.get("CARLA_HOST"))
    parser.add_argument("--port", type=int, default=os.environ.get("CARLA_PORT"))
    parser.add_argument("--candidate", choices=("primary", "fallback1"))
    args = parser.parse_args()
    case_id = check()
    candidate = json.loads((ROOT / "config.json").read_text(encoding="utf-8")).get("candidate_id", "primary")
    if args.candidate is not None and args.candidate != candidate:
        raise ValueError("selected candidate differs from bound construction")
    if args.check:
        print("exact projection bundle passed: " + case_id)
        return
    if not all((args.reviewed_packet, args.adapter_module, args.output_dir,
                args.host, args.port)):
        raise ValueError("reviewed packet, Native adapter and endpoint required")
    packet, _ = load_reviewed(args.reviewed_packet, case_id)
    module_path = validate_native_adapter(packet, args.adapter_module)
    spec = importlib.util.spec_from_file_location("projection_native_adapter", module_path)
    if spec is None or spec.loader is None:
        raise ValueError("original Native adapter module missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter = module.open_native_adapter(args.host, args.port)
    try:
        print(capture_original(adapter, args.reviewed_packet, case_id, args.output_dir,
                               candidate=candidate, adapter_module_path=module_path))
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
