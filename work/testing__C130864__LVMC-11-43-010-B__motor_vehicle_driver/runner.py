"""Exact source-gated Native entrypoint for a materialized roundabout case."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from capture_roundabout import CAMERA_DIMENSIONS
from roundabout_measurements import ASSIGNMENT_ID, SUFFIXES


def check(directory):
    root = Path(directory).resolve()
    config = json.loads((root / "config.json").read_text())
    spec = json.loads((root / "case-spec.json").read_text())
    controller = json.loads((root / "controller.json").read_text())
    case_id = config.get("selected_case_id")
    if case_id not in {ASSIGNMENT_ID + "__" + name for name in SUFFIXES} or (
            spec.get("case_id") != case_id or
            (config.get("law_id"), config.get("cell_id"), config.get("actor")) !=
            ("LVMC-11-43-010-B", "C130864", "motor_vehicle_driver")):
        raise ValueError("materialized exact roundabout case identity differs")
    cameras = config.get("cameras", [])
    named = {row.get("name"): [row.get("width"), row.get("height")]
             for row in cameras if isinstance(row, dict)}
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45 or (
            len(cameras) != 4 or named !=
            {name: list(size) for name, size in CAMERA_DIMENSIONS.items()}):
        raise ValueError("materialized original four-camera capture profile differs")
    if spec.get("opponent_lane_relation") not in ("connected", "adjacent") or (
            spec.get("planned_gap_condition") not in ("near", "wider") or
            spec.get("ego_entry_request") not in ("wait", "enter")):
        raise ValueError("exact roundabout comparison variables missing")
    if not case_id.endswith("__" + ("connected_gap_" if spec["planned_gap_condition"] == "wider"
                                    else spec["opponent_lane_relation"] + "_") +
                            spec["ego_entry_request"]):
        raise ValueError("exact case distinction differs")
    throttle = controller.get("throttle")
    if type(throttle) not in (int, float) or not 0 < throttle <= .5:
        raise ValueError("bounded vehicle controller throttle required")
    return {"case_id": case_id, "throttle": float(throttle),
            "source_gate": "reviewed original C130864 roundabout map and route packet required before Native"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    parser.add_argument("--site-review", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    selected = check(args.output_dir)
    if args.check:
        print(json.dumps({**selected, "static_construction_valid": True,
                          "native_started": False}))
        return 0
    source = args.site_review or os.environ.get("C130864_ROUNDABOUT_REVIEW")
    if not source:
        raise ValueError("Missing required source: reviewed original C130864 roundabout map and route packet")
    from native_entry import run_native
    result = run_native(source, selected["case_id"], args.output_dir,
                        host=args.host, port=args.port, throttle=selected["throttle"])
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
