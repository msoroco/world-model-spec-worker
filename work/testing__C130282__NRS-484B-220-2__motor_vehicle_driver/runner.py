"""Exact rotary-island construction: static check or source-gated Native launch."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from island_measurements import ASSIGNMENT_ID, SUFFIXES
from island_source import CAMERAS, DIMENSIONS, load_reviewed


def check(directory):
    root = Path(directory).resolve()
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    case_id = config.get("selected_case_id")
    if (case_id not in {ASSIGNMENT_ID + "__" + suffix for suffix in SUFFIXES} or
            (config.get("law_id"), config.get("cell_id"), config.get("actor")) !=
            ("NRS-484B-220-2", "C130282", "motor_vehicle_driver")):
        raise ValueError("exact selected rotary-island case identity required")
    lane, side = case_id.rsplit("__", 1)[1].split("_")
    if (config.get("circulation_lane_role"), config.get("requested_island_side")) != (lane, side):
        raise ValueError("exact case variables differ")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("original 20 Hz / 45-second capture required")
    cameras = config.get("cameras")
    if not isinstance(cameras, list) or len(cameras) != 4 or {
            row.get("name"): (row.get("width"), row.get("height")) for row in cameras} != DIMENSIONS:
        raise ValueError("four original camera profile required")
    controller = json.loads((root / "controller.json").read_text(encoding="utf-8"))
    throttle = controller.get("throttle")
    if type(throttle) not in (int, float) or not 0 < throttle <= .5:
        raise ValueError("bounded engineering throttle required")
    return {"case_id": case_id, "throttle": float(throttle),
            "source_gate": "reviewed original rotary-island identity, physical polygon, map and connected routes required"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    parser.add_argument("--island-review", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    selected = check(args.output_dir)
    if args.check:
        print(json.dumps({**selected, "native_started": False, "static_construction_valid": True}))
        return 0
    source = args.island_review or os.environ.get("C130282_ISLAND_REVIEW")
    if not source:
        raise ValueError("missing reviewed original rotary-island source packet")
    load_reviewed(source, selected["case_id"])
    from native_island_entry import run_native
    result = run_native(source, selected["case_id"], args.output_dir,
                        host=args.host, port=args.port, throttle=selected["throttle"])
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
