"""Source-gated exact yield construction; --check runs without CARLA."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from yield_site import ASSIGNMENT
from yield_source import DIMENSIONS, SUFFIXES, load_reviewed


def check(root):
    root = Path(root)
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    case_id = config.get("selected_case_id")
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("exact selected yield case required")
    if (config.get("assignment_id"), config.get("law_id"), config.get("cell_id"),
            config.get("actor")) != (ASSIGNMENT, "NRS-484A-450-3", "C24823", "motor_vehicle_driver"):
        raise ValueError("exact assignment scope differs")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("original 20 Hz / 45-second capture required")
    if {row["name"]: (row["width"], row["height"]) for row in config.get("cameras", [])} != DIMENSIONS:
        raise ValueError("four-camera capability profile required")
    controller = json.loads((root / "controller.json").read_text(encoding="utf-8"))
    if controller.get("target_behavior") != case_id.rsplit("__", 1)[1]:
        raise ValueError("exact stop behavior differs")
    throttle = controller.get("throttle")
    if type(throttle) not in (float, int) or not 0 < throttle <= .5:
        raise ValueError("bounded engineering throttle required")
    return {"case_id": case_id, "throttle": float(throttle),
            "source_gate": "reviewed original yield sign, map, crossing inventory, sight geometry, safety context and four-camera placement required"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--yield-review")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    selected = check(args.output_dir)
    if args.check:
        print(json.dumps({**selected, "native_started": False, "static_construction_valid": True}))
        return 0
    source = args.yield_review or os.environ.get("C24823_YIELD_REVIEW")
    if not source:
        raise ValueError("reviewed original yield source packet required")
    reviewed = load_reviewed(source, selected["case_id"])
    from native_yield_entry import run_native
    print(json.dumps(run_native(reviewed, selected["case_id"], args.output_dir,
                                host=args.host, port=args.port, throttle=selected["throttle"]), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
