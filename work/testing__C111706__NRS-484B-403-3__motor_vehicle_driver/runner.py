"""Exact source-gated Native entrypoint for C111706 U-turn deliveries."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C111706__NRS-484B-403-3__motor_vehicle_driver"
SUFFIXES = ("intersection_vehicle_near", "approach_before_intersection",
            "intersection_vehicle_far")
CASES = {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES}


def check(root=ROOT):
    root = Path(root)
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    if (config.get("assignment_id"), config.get("law_id"),
            config.get("cell_id"), config.get("actor")) != (
            ASSIGNMENT, "NRS-484B-403-3", "C111706", "motor_vehicle_driver"):
        raise ValueError("wrong exact U-turn package identity")
    selected = config.get("selected_case_id")
    if selected not in CASES or set(config.get("supported_case_ids", [])) != CASES:
        raise ValueError("exact U-turn case selection differs")
    if (config.get("rate_hz"), config.get("duration_s"),
            config.get("frame_count")) != (20, 45, 900):
        raise ValueError("exact U-turn capture timebase differs")
    cameras = config.get("cameras", [])
    if [(c.get("name"), c.get("width"), c.get("height")) for c in cameras] != [
            ("overview", 1920, 1080), ("approach", 1280, 720),
            ("reference_corner", 1280, 720),
            ("driver_reference", 1280, 720)]:
        raise ValueError("four original cameras required")
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    selected = check()
    if args.check:
        return 0
    if args.output_dir is None:
        raise ValueError("new Native output directory required")
    site_root = os.environ.get("C111706_SITE_ROOT")
    if not site_root:
        raise ValueError("C111706_SITE_ROOT reviewed site directory required")
    site_path = Path(site_root) / (selected.split("__")[-1] + ".json")
    if not site_path.is_file() or site_path.is_symlink():
        raise ValueError("exact reviewed site packet required")
    from live_entrypoint import run
    run(host=args.host, port=args.port, site_path=site_path,
        case_id=selected, output=args.output_dir / "capture" / "native-uturn.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
