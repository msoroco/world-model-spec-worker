"""Source-gated Native acquisition for the exact two-way obstruction cases."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from reviewed_scene import ASSIGNMENT, VARIANTS, execute_native, plan


def check_config(config: dict) -> None:
    case_id = config.get("selected_case_id", "")
    if (case_id not in {ASSIGNMENT + "__" + suffix for suffix in VARIANTS} or
            config.get("law_id") != "NRS-484B-627-1a" or
            config.get("cell_id") != "C323986" or
            config.get("actor") != "motor_vehicle_driver"):
        raise ValueError("exact assignment or case identity mismatch")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("20 Hz 45-second capture contract required")
    cameras = config.get("cameras", [])
    if [(c.get("name"), c.get("width"), c.get("height")) for c in cameras] != [
            ("overview", 1920, 1080), ("approach", 1280, 720),
            ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]:
        raise ValueError("four-view capture profile mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    check_config(config)
    if args.check:
        print("exact source-gated construction configuration passed")
        return
    if args.output_dir is None or args.output_dir.exists():
        raise ValueError("fresh Native attempt output directory required")
    authority = os.environ.get("C323986_AUTHORITY_ROOT")
    ref_path = os.environ.get("C323986_SITE_REF")
    if not authority or not ref_path:
        raise ValueError("reviewed original highway site source required")
    site_ref = json.loads(Path(ref_path).read_text(encoding="utf-8"))
    scene = plan(Path(authority), site_ref, config["selected_case_id"])
    args.output_dir.mkdir(parents=True)
    from native_adapter import NativeAdapter
    adapter = NativeAdapter(args.host, args.port, args.output_dir)
    adapter.site_road_id = scene["road_id"]
    adapter.assignment_id = ASSIGNMENT
    adapter.case_id = scene["case_id"]
    adapter.trace_id = args.output_dir.name
    try:
        execute_native(scene, adapter)
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
