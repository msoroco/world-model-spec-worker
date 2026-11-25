"""Exact-case source-gated Native acquisition entrypoint."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from reviewed_scene import ASSIGNMENT, plan, execute_native


def check_config(config: dict):
    if config.get("selected_case_id", "").removeprefix(ASSIGNMENT + "__") not in (
        "slow_middle_follower", "slow_right_follower", "slow_middle_passing",
        "slow_middle_no_immediate_follower"):
        raise ValueError("unassigned selected case")
    if config.get("diagnostic_only") is not True or config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("diagnostic capture contract mismatch")
    if set(config.get("cameras", [])) != {"overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four-camera contract mismatch")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    check_config(config)
    if args.check:
        print("diagnostic construction contract passed")
        return
    if args.output_dir is None:
        raise ValueError("Native attempt output directory required")
    root = os.environ.get("C147344_AUTHORITY_ROOT")
    ref_path = os.environ.get("C147344_SITE_REF")
    if not root or not ref_path:
        raise ValueError("original reviewed site source paths required")
    site_ref = json.loads(Path(ref_path).read_text(encoding="utf-8"))
    scene = plan(Path(root), site_ref, config["selected_case_id"])
    site = json.loads((Path(root) / site_ref["path"]).read_text(encoding="utf-8"))
    from native_adapter import NativeAdapter
    adapter = NativeAdapter(args.host, args.port, args.output_dir)
    adapter.site_road_id = site["road_id"]
    adapter.assignment_id = ASSIGNMENT
    adapter.case_id = config["selected_case_id"]
    adapter.trace_id = args.output_dir.name
    adapter.rightmost_lane_id = scene["rightmost_lane_id"]
    adapter.marked_lane_count = len(site["same_direction_lanes"])
    try:
        execute_native(scene, adapter)
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
