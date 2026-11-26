"""Exact-case source-gated Native pedestrian signal acquisition entrypoint."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from ped_entry import CASES, construct
from reviewed_scene import plan


ASSIGNMENT = "testing__C227824__NRS-484B-307-9c__pedestrian"
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def check_config(config: dict) -> bool:
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-307-9c", "C227824", "pedestrian"):
        raise ValueError("exact pedestrian assignment identity differs")
    if config.get("selected_case_id") not in {
            ASSIGNMENT + "__" + case.case_id for case in CASES}:
        raise ValueError("unassigned selected signal-entry case")
    if (config.get("diagnostic_only") is not True or
            config.get("rate_hz") != 20 or config.get("duration_s") != 45 or
            set(config.get("cameras", [])) != CAMERAS):
        raise ValueError("four-camera 900-frame capture contract differs")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    check_config(config)
    if args.check:
        print("exact pedestrian signal construction contract passed")
        return
    if args.output_dir is None or args.output_dir.exists():
        raise ValueError("fresh original Native attempt output required")
    root = os.environ.get("C227824_AUTHORITY_ROOT")
    ref_path = os.environ.get("C227824_SITE_REF")
    if not root or not ref_path:
        raise ValueError("reviewed original signal site source paths required")
    site_ref = json.loads(Path(ref_path).read_text(encoding="utf-8"))
    scene_plan = plan(Path(root), site_ref, config["selected_case_id"])
    from native_adapter import NativeAdapter
    adapter = NativeAdapter(args.host, args.port, args.output_dir, scene_plan)
    try:
        adapter.open_map()
        constructed = construct(adapter, scene_plan["scene"], scene_plan["case"])
        adapter.attach_cameras(constructed["owned"][0])
        for index in range(900):
            adapter.tick_and_capture(index)
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
