"""Exact school pedestrian-lane Native capture entrypoint."""

import argparse
import json
import os
from pathlib import Path

from package_contract import ACTOR, CAMERAS, CELL, LAW
from reviewed_site import plan
from school_lane_controls import selected_schedule


HERE = Path(__file__).resolve().parent


def selected_ids():
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    return {case["case_id"] for case in proposal["cases"] if case.get("target_law_id") == LAW}


def check_config(config):
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (LAW, CELL, ACTOR):
        raise ValueError("exact school-lane assignment identity differs")
    case_id = config.get("selected_case_id")
    if case_id not in selected_ids():
        raise ValueError("unselected exact school-lane case")
    if (config.get("diagnostic_only") is not True or config.get("rate_hz") != 20 or
            config.get("duration_s") != 45 or config.get("cameras") != CAMERAS):
        raise ValueError("four-camera 900-frame original capture contract differs")
    selected_schedule(case_id, 0.0)
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
        print("exact source-gated school-lane construction contract passed")
        return
    if args.output_dir is None or args.output_dir.exists():
        raise ValueError("fresh original Native attempt output required")
    authority_root = os.environ.get("C422976_AUTHORITY_ROOT")
    site_ref_path = os.environ.get("C422976_SITE_REF")
    if not authority_root or not site_ref_path:
        raise ValueError("reviewed original school-lane site source required")
    site_ref = json.loads(Path(site_ref_path).read_text(encoding="utf-8"))
    scene = plan(Path(authority_root), site_ref, config["selected_case_id"])
    from native_adapter import NativeAdapter
    adapter = NativeAdapter(args.host, args.port, args.output_dir, scene)
    try:
        adapter.open_map()
        adapter.construct()
        for frame in range(900):
            adapter.tick_and_capture(frame)
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
